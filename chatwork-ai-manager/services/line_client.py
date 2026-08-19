"""LINE Messaging API クライアント（標準ライブラリのみ・依存追加なし）。

- 署名検証: X-Line-Signature = base64(HMAC-SHA256(channel_secret, request_body))
- reply: 受信直後の即時返信（reply_token・1回・短命）
- push:  任意タイミングの送信（userId宛。長時間処理の結果通知に使う）
- userId 許可制: line_allowed_user_ids（カンマ区切り）に含まれる者だけ Agent へ通す
"""
import base64
import hashlib
import hmac
import json
import urllib.request

from services import config

REPLY_URL = "https://api.line.me/v2/bot/message/reply"
PUSH_URL = "https://api.line.me/v2/bot/message/push"


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


def _post(url: str, payload: dict) -> bool:
    token = config.get("line_channel_access_token")
    if not token:
        return False
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data, method="POST",
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status == 200
    except Exception:
        return False


def _text_messages(text: str):
    # LINEは1メッセージ5000文字上限。長文は分割（最大5通/リクエスト）。
    chunks = [text[i:i + 4800] for i in range(0, len(text), 4800)] or [""]
    return [{"type": "text", "text": c} for c in chunks[:5]]


def reply(reply_token: str, text: str) -> bool:
    return _post(REPLY_URL, {"replyToken": reply_token, "messages": _text_messages(text)})


def push(user_id: str, text: str) -> bool:
    return _post(PUSH_URL, {"to": user_id, "messages": _text_messages(text)})


def push_image(user_id: str, image_url: str) -> bool:
    """画像メッセージをpushする。image_url はHTTPS・LINE側から到達可能な公開URLが必要
    （originalContentUrl/previewImageUrlとも同じURLを使う。JPEG/PNG・10MBまで）。"""
    return _post(PUSH_URL, {"to": user_id, "messages": [
        {"type": "image", "originalContentUrl": image_url, "previewImageUrl": image_url},
    ]})
