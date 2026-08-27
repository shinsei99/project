"""LINE Messaging API クライアント（標準ライブラリのみ・依存追加なし）。

- 署名検証: X-Line-Signature = base64(HMAC-SHA256(channel_secret, request_body))
- reply: 受信直後の即時返信（reply_token・1回・短命）。**無料枠を消費しない**
- push:  任意タイミングの送信（userId宛。長時間処理の結果通知に使う）。**無料枠を消費する**
- userId 許可制: line_allowed_user_ids（カンマ区切り）に含まれる者だけ Agent へ通す

## 送信可能メッセージ数（2026-08-20の障害でここが原因になった）

LINE公式アカウントで課金対象なのは **push だけ**（reply は無料・無制限）。
コミュニケーションプラン(無料)は 200通/月しかなく、実測 1日約50通で **4日で枯渇**した。
枯渇すると push は HTTP 429 を返して届かなくなるが、**利用者から見ると「無反応」**に
しか見えない。以前の `_post()` は `except Exception: return False` で理由を捨てて
いたため、誰も原因に気づけなかった。→ 失敗は必ず理由を残し、`last_error()` で読める。

送信数は「メッセージオブジェクト単位」で数えられる。長文を `_text_messages()` が
4800文字ごとに分割すると、**1回の push で複数通を消費する**ことに注意。
"""
import base64
import hashlib
import hmac
import json
import threading
import urllib.error
import urllib.request

from services import config

REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PUSH_URL = "https://api.line.me/v2/bot/message/push"
QUOTA_URL = "https://api.line.me/v2/bot/message/quota"
CONSUMPTION_URL = "https://api.line.me/v2/bot/message/quota/consumption"

# 枠切れを検知したことを記録する state キー（worker が拾って Chatwork へ知らせる）
QUOTA_EXHAUSTED = "line_quota_exhausted"
QUOTA_EXHAUSTED_AT = "line_quota_exhausted_at"

_last_error = None
_lock = threading.Lock()


def last_error():
    """直近の送信失敗の理由（dict）。成功していれば None。"""
    with _lock:
        return dict(_last_error) if _last_error else None


def _record_error(kind: str, status=None, body: str = "", exc: str = ""):
    global _last_error
    with _lock:
        _last_error = {"kind": kind, "status": status, "body": body[:300], "exc": exc}
    print(f"[line] 送信失敗 kind={kind} status={status} body={body[:200]} {exc}", flush=True)


def _clear_error():
    global _last_error
    with _lock:
        _last_error = None


def verify_signature(body_bytes: bytes, signature: str) -> bool:
    secret = config.get("line_channel_secret")
    if not secret or not signature:
        return False
    mac = hmac.new(str(secret).encode("utf-8"), body_bytes, hashlib.sha256).digest()
    expected = base64.b64encode(mac).decode("utf-8")
    return hmac.compare_digest(expected, signature)


def allowed_user_ids() -> set:
    raw = config.get("line_allowed_user_ids", "") or ""
    return {u.strip() for u in str(raw).split(",") if u.strip()}


def is_allowed(user_id: str) -> bool:
    allow = allowed_user_ids()
    # 未設定なら「誰も許可しない」（安全側）。運用開始時に自分のuserIdを登録する。
    return bool(user_id) and user_id in allow


def _mark_quota_exhausted(reason: str):
    """枠切れをDBに記録する。worker がこれを見て Chatwork へ知らせる。"""
    try:
        from services import settings
        import datetime
        if settings.get_state(QUOTA_EXHAUSTED, "0") != "1":
            settings.set_state(QUOTA_EXHAUSTED_AT,
                               datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
        settings.set_state(QUOTA_EXHAUSTED, "1")
    except Exception as e:      # DBが無い状況でも送信処理自体は止めない
        print(f"[line] 枠切れの記録に失敗: {type(e).__name__}: {e}", flush=True)
    print(f"[line] ★送信可能メッセージ数の上限に達しています: {reason}", flush=True)


def _clear_quota_exhausted():
    try:
        from services import settings
        if settings.get_state(QUOTA_EXHAUSTED, "0") == "1":
            settings.set_state(QUOTA_EXHAUSTED, "0")
            print("[line] 送信可能メッセージ数が回復しました。", flush=True)
    except Exception:
        pass


def quota_exhausted() -> bool:
    try:
        from services import settings
        return settings.get_state(QUOTA_EXHAUSTED, "0") == "1"
    except Exception:
        return False


def _auth_headers():
    token = config.get("line_channel_access_token")
    if not token:
        return None
    return {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}


def _post(url: str, payload: dict, label: str = "", want_body: bool = False):
    """LINEへ送信する。失敗しても例外は投げないが、**理由は必ず残す**。

    label は呼び出し元の名前（'qa_answer' など）。どの経路が枠を食っているかを
    ログから数えられるようにするために受ける。
    """
    headers = _auth_headers()
    if headers is None:
        _record_error("no_token", body="line_channel_access_token が未設定")
        return None if want_body else False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST", headers=headers)
    n = len(payload.get("messages") or [])
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            ok = resp.status == 200
            raw = b""
            if ok:
                try:
                    raw = resp.read()
                except Exception:
                    raw = b""
                _clear_error()
                if url == PUSH_URL:
                    # 送信通数の内訳を数えられるようにする（メッセージ単位＝課金単位）
                    print(f"[line] push ok label={label or '-'} messages={n}", flush=True)
                    _clear_quota_exhausted()
            else:
                _record_error("bad_status", status=resp.status, body=str(resp.status))
            if want_body:
                try:
                    return json.loads(raw.decode("utf-8")) if ok and raw else ({} if ok else None)
                except Exception:
                    return {} if ok else None
            return ok
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            pass
        # 429 = 送信可能メッセージ数の上限（月の無料枠切れ）。これが2026-08-20の原因。
        if e.code == 429 or "monthly limit" in body.lower():
            _mark_quota_exhausted(body or "HTTP 429")
            _record_error("quota_exhausted", status=e.code, body=body)
        elif e.code in (401, 403):
            _record_error("auth", status=e.code, body=body)
        else:
            _record_error("http_error", status=e.code, body=body)
        print(f"[line] push 失敗 label={label or '-'} messages={n} status={e.code}", flush=True)
        return False
    except Exception as e:
        _record_error("exception", exc=f"{type(e).__name__}: {e}")
        return False


def _get(url: str):
    headers = _auth_headers()
    if headers is None:
        return None
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except Exception as e:
        print(f"[line] 取得失敗 {url}: {type(e).__name__}: {e}", flush=True)
        return None


def quota() -> dict:
    """今月の送信可能メッセージ数と消費量を返す。

    返り値: {"limit": int|None, "used": int|None, "remaining": int|None, "type": str}
    limit が None は「無制限（type='none'）」か取得失敗。取得失敗時は type='unknown'。
    """
    q = _get(QUOTA_URL)
    c = _get(CONSUMPTION_URL)
    if q is None or c is None:
        return {"limit": None, "used": None, "remaining": None, "type": "unknown"}
    qtype = q.get("type") or "unknown"
    limit = q.get("value") if qtype == "limited" else None
    used = c.get("totalUsage")
    remaining = None
    if isinstance(limit, int) and isinstance(used, int):
        remaining = max(0, limit - used)
    return {"limit": limit, "used": used, "remaining": remaining, "type": qtype}


def _text_messages(text: str):
    # LINEは1メッセージ5000文字上限。長文は分割（最大5通/リクエスト）。
    # 分割した数だけ送信可能メッセージ数を消費する（＝長い回答ほど枠を食う）。
    chunks = [text[i:i + 4800] for i in range(0, len(text), 4800)] or [""]
    return [{"type": "text", "text": c} for c in chunks[:5]]


def reply(reply_token: str, text: str) -> bool:
    """reply_token での返信。**無料枠を消費しない**ので、枠切れ中でも届く。"""
    return _post(REPLY_URL, {"replyToken": reply_token, "messages": _text_messages(text)},
                 label="reply")


def push(user_id: str, text: str, label: str = "") -> bool:
    return _post(PUSH_URL, {"to": user_id, "messages": _text_messages(text)},
                 label=label or "push")


def push_image(user_id: str, image_url: str, label: str = "", with_id: bool = False):
    """画像メッセージをpushする。image_url はHTTPS・LINE側から到達可能な公開URLが必要
    （originalContentUrl/previewImageUrlとも同じURLを使う。JPEG/PNG・10MBまで）。

    `with_id=True` のとき **(成功したか, 送ったメッセージのID)** を返す。
    利用者がLINEの「リプライ」でその写真を引用したとき、webhookに届く
    `quotedMessageId` と突き合わせて「どの写真の話か」を特定するために要る
    （2026-08-27。これが無いと、写真を引用して「◯◯です」と言われても分からない）。
    """
    payload = {"to": user_id, "messages": [
        {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url},
    ]}
    if not with_id:
        return _post(PUSH_URL, payload, label=label or "push_image")
    body = _post(PUSH_URL, payload, label=label or "push_image", want_body=True)
    if body is None:
        return False, None
    sent = (body or {}).get("sentMessages") or []
    return True, (sent[0].get("id") if sent else None)
