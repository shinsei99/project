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

    def post_message(self, room_id: int, body: str, self_unread: bool = False) -> str:
        """メッセージ投稿。戻り値: 作成された message_id。"""
        data = {"body": body, "self_unread": 1 if self_unread else 0}
        res = self._request("POST", f"/rooms/{room_id}/messages", data=data)
        return str(res.get("message_id")) if isinstance(res, dict) else None


def mention(account_id, name: str = None) -> str:
    """Chatwork のメンション記法 [To:account_id] を生成。"""
    tag = f"[To:{account_id}]"
    return f"{tag}{name} さん" if name else tag
