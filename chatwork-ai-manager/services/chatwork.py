"""Chatwork API v2 クライアント（標準ライブラリ urllib のみ・依存追加なし）。

- 認証: X-ChatworkToken ヘッダ
- レート制限: 300req/5min。x-ratelimit-remaining/reset を見て、429 は reset まで待って 1 度だけ再試行。
- 取得境界（last_message_id）は呼び出し側（poller）で管理し、force=1 で最新100件を取得する。
"""
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from services import config

BASE_URL = "https://api.chatwork.com/v2"


class ChatworkError(RuntimeError):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status


class ChatworkClient:
    def __init__(self, token: str = None, timeout: int = 30):
        self.token = token or config.chatwork_token()
        self.timeout = timeout
        # レート制限の残数（ヘッダから更新）
        self.rate_remaining = None
        self.rate_reset = None

    # ---- 低レベル ----
    def _request(self, method: str, path: str, params=None, data=None, _retry=True):
        url = f"{BASE_URL}{path}"
        body = None
        headers = {"X-ChatworkToken": self.token, "Accept": "application/json"}
        if method == "GET" and params:
            url += "?" + urllib.parse.urlencode(params)
        if data is not None:
            body = urllib.parse.urlencode(data).encode("utf-8")
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                self._update_rate(resp.headers)
                if resp.status == 204:
                    return []
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else None
        except urllib.error.HTTPError as e:
            self._update_rate(e.headers)
            if e.code == 429 and _retry:
                wait = self._retry_wait()
                time.sleep(wait)
                return self._request(method, path, params=params, data=data, _retry=False)
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise ChatworkError(f"Chatwork API {e.code} {path}: {detail}", status=e.code)
        except urllib.error.URLError as e:
            raise ChatworkError(f"Chatwork 接続失敗 {path}: {e.reason}")

    def _update_rate(self, headers):
        try:
            rem = headers.get("x-ratelimit-remaining")
            rst = headers.get("x-ratelimit-reset")
            if rem is not None:
                self.rate_remaining = int(rem)
            if rst is not None:
                self.rate_reset = int(rst)
        except (TypeError, ValueError):
            pass

    def _retry_wait(self) -> float:
        if self.rate_reset:
            return max(1.0, self.rate_reset - time.time() + 1)
        return 30.0

    # ---- 高レベル API ----
    def get_me(self) -> dict:
        return self._request("GET", "/me")

    def get_rooms(self) -> list:
        return self._request("GET", "/rooms") or []

    def get_members(self, room_id: int) -> list:
        return self._request("GET", f"/rooms/{room_id}/members") or []

    def get_messages(self, room_id: int, force: bool = True) -> list:
        """ルームのメッセージを取得（最大100件）。force=True で最新を強制取得。

        新規が無い場合 Chatwork は 204 を返すため空リストになる。
        """
        params = {"force": 1 if force else 0}
        return self._request("GET", f"/rooms/{room_id}/messages", params=params) or []

    def get_file(self, room_id: int, file_id: int) -> dict:
        """アップロードされたファイルの情報を取る。

        `create_download_url=1` を付けると `download_url` が入る（**有効期限30秒**）。
        取ったらすぐ落とすこと。
        """
        return self._request("GET", f"/rooms/{room_id}/files/{file_id}",
                             params={"create_download_url": 1}) or {}

    def download_file(self, room_id: int, file_id: int):
        """ファイル本体をダウンロードする。戻り値: (bytes, filename)。

        get_file の download_url は署名付きURLで**有効期限30秒**なので、
        取得したその場ですぐ読みに行く（トークンヘッダは付けない＝Chatwork API側ではない）。
        """
        info = self.get_file(room_id, file_id)
        url = info.get("download_url")
        if not url:
            return None, info.get("filename")
        req = urllib.request.Request(url, headers={"Accept": "*/*"})
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            return resp.read(), info.get("filename") or f"file_{file_id}"

    def post_message(self, room_id: int, body: str, self_unread: bool = False) -> str:
        """メッセージ投稿。戻り値: 作成された message_id。"""
        data = {"body": body, "self_unread": 1 if self_unread else 0}
        res = self._request("POST", f"/rooms/{room_id}/messages", data=data)
        return str(res.get("message_id")) if isinstance(res, dict) else None

    def delete_message(self, room_id: int, message_id) -> None:
        """メッセージを削除する（TASK-20260828-001で調査）。

        Chatwork API v2 には**ファイル単体を削除するエンドポイントが無い**
        （/rooms/{id}/files は GET・POSTのみ。公式ドキュメントで確認済み）。
        ファイルは投稿時に自動生成されるメッセージに紐付いており、消す手段はこの
        メッセージ削除APIしか無い。ただし**トークン所有アカウント自身が投稿した
        メッセージしか削除できない**（他人のメッセージは403 "You can only edit
        the message you sent."。room管理者による例外もドキュメントに無い）。
        """
        self._request("DELETE", f"/rooms/{room_id}/messages/{message_id}")

    def post_file(self, room_id: int, file_path: str, message: str = None,
                  filename: str = None) -> str:
        """ファイルを添付投稿する。戻り値: 作成された file_id。

        Chatwork の /rooms/{id}/files は **multipart/form-data 限定**（他のAPIのような
        urlencode では通らない）ため、ここだけ独自に本文を組み立てる。
        依存を増やさない方針なので requests は使わず標準ライブラリで作る。

        **上限5MB**（Chatwork側の制限）。超えるものは呼ぶ前に弾くこと。
        """
        import mimetypes
        import os
        import uuid

        name = filename or os.path.basename(file_path)
        with open(file_path, "rb") as f:
            payload = f.read()
        ctype = mimetypes.guess_type(name)[0] or "application/octet-stream"
        boundary = "----cwai" + uuid.uuid4().hex

        def _part(header: str, value: bytes) -> bytes:
            return (f"--{boundary}\r\n{header}\r\n\r\n").encode("utf-8") + value + b"\r\n"

        body = b""
        if message:
            body += _part('Content-Disposition: form-data; name="message"',
                          message.encode("utf-8"))
        # ファイル名は **生の UTF-8 のまま** 入れる。
        # ここは実地で確かめた（2026-08-19）: RFC2231 の filename*=UTF-8''… も一緒に付けて
        # filename= 側をパーセントエンコードしたところ、Chatwork は filename= の値を
        # そのまま採用し、受信側に「%E3%82%B0…jpg」という名前で見えてしまった。
        # Chatwork は filename= の生UTF-8を正しく扱えるので、素直にそれだけを渡す。
        safe_name = name.replace('"', "").replace("\r", "").replace("\n", "")
        body += _part(
            f'Content-Disposition: form-data; name="file"; filename="{safe_name}"\r\n'
            f"Content-Type: {ctype}", payload)
        body += f"--{boundary}--\r\n".encode("utf-8")

        url = f"{BASE_URL}/rooms/{room_id}/files"
        headers = {"X-ChatworkToken": self.token, "Accept": "application/json",
                   "Content-Type": f"multipart/form-data; boundary={boundary}"}
        req = urllib.request.Request(url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=max(self.timeout, 120)) as resp:
                self._update_rate(resp.headers)
                raw = resp.read().decode("utf-8")
                res = json.loads(raw) if raw else {}
                return str(res.get("file_id")) if isinstance(res, dict) else None
        except urllib.error.HTTPError as e:
            self._update_rate(e.headers)
            detail = ""
            try:
                detail = e.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise ChatworkError(f"Chatwork ファイル送信 {e.code}: {detail}", status=e.code)
        except urllib.error.URLError as e:
            raise ChatworkError(f"Chatwork 接続失敗（ファイル送信）: {e.reason}")


def mention(account_id, name: str = None) -> str:
    """Chatwork のメンション記法 [To:account_id] を生成。"""
    tag = f"[To:{account_id}]"
    return f"{tag}{name} さん" if name else tag
