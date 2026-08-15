#!/usr/bin/env python3
"""LINE Webhook 受信サーバー（第2の入口・標準ライブラリのみ）。

フロー:
  LINE → POST /line/webhook → 署名検証 → 即200 → （裏スレッドで）
    userId許可チェック → reply「調べています…」→ 共通Agent qa.answer(channel='line') → push(結果)

重要:
  - LINE専用のAI/Tool/DBは作らない。Chatworkと同じ qa.answer / agent_tools / DB を使う。
  - Webhookタイムアウト回避のため受信は即200、処理は別スレッド、結果は push で通知。
  - 未登録userIdは Agent へ到達させない（安全側: 許可リスト未設定なら全員拒否）。
  - port 8530。公開HTTPS(Cloudflare Tunnel)経由でLINEプラットフォームから届く。
"""
import json
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_conn  # noqa: E402
from db.migrate import migrate  # noqa: E402
from services import line_client, qa  # noqa: E402

PORT = int(os.environ.get("CWAI_LINE_PORT", "8530"))


def _log_line(user_id, text, reply_text=None, note=None):
    try:
        with get_conn() as c:
            c.execute(
                "INSERT INTO ai_analysis_logs (kind, model, prompt, raw_output, error) "
                "VALUES ('line', 'sonnet', ?, ?, ?)",
                (f"[{user_id}] {text}", reply_text, note),
            )
    except Exception:
        pass


def _handle_event(ev):
    """1つのLINEイベントを処理（別スレッドで実行）。"""
    if ev.get("type") != "message":
        return
    msg = ev.get("message", {})
    if msg.get("type") != "text":
        return
    source = ev.get("source", {})
    user_id = source.get("userId")
    reply_token = ev.get("replyToken")
    text = (msg.get("text") or "").strip()

    if not line_client.is_allowed(user_id):
        _log_line(user_id, text, note="未登録userId（拒否）")
        if reply_token:
            line_client.reply(reply_token, "このアカウントは未登録のため利用できません。")
        return

    # 即時ack（reply_tokenは短命・1回）。処理は続けてpushで返す。
    if reply_token:
        line_client.reply(reply_token, "受け付けました。調べています…🔎")

    try:
        res = qa.answer(text, channel="line", asker="オーナー(LINE)")
        answer_text = res.get("answer") or "（回答を生成できませんでした）"
    except Exception as e:
        answer_text = f"処理中にエラーが発生しました: {type(e).__name__}"
        _log_line(user_id, text, note=str(e))
    line_client.push(user_id, answer_text)
    _log_line(user_id, text, reply_text=answer_text)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass  # デフォルトの標準エラー出力を抑制

    def _send(self, code=200, body=b"OK"):
        self.send_response(code)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        # 疎通確認用
        if self.path in ("/", "/health", "/line/health"):
            self._send(200, b"line-webhook ok")
        else:
            self._send(404, b"not found")

    def do_POST(self):
        if self.path != "/line/webhook":
            self._send(404, b"not found")
            return
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        signature = self.headers.get("X-Line-Signature", "")
        if not line_client.verify_signature(body, signature):
            self._send(403, b"invalid signature")
            return
        # 署名OK: 即200を返し、処理は裏スレッドへ（タイムアウト回避）
        self._send(200, b"OK")
        try:
            payload = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError:
            return
        for ev in payload.get("events", []):
            threading.Thread(target=_handle_event, args=(ev,), daemon=True).start()


def main():
    migrate()
    print(f"[line-webhook] listening on :{PORT}  (POST /line/webhook)", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
