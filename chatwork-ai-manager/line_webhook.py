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
from services import (admin_ops, attachments, claude_health, config,  # noqa: E402
                      line_client, pending, qa)
from services.claude_client import ClaudeStalledError  # noqa: E402

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


def _is_admin(user_id: str) -> bool:
    """常駐の再起動を許すのは管理者だけ。

    `line_admin_user_ids` が未設定なら、いまの許可ユーザー（=本人）と同じ扱いにする。
    """
    raw = config.get("line_admin_user_ids", "") or ""
    admins = {u.strip() for u in str(raw).split(",") if u.strip()}
    return user_id in admins if admins else line_client.is_allowed(user_id)


def _monthly_report_result_text(result) -> str:
    if result["errors"] and "row" not in result:
        return "⚠️ 月報を作成できませんでした:\n- " + "\n- ".join(result["errors"])
    if result["errors"]:
        return ("📝 業務月報を作成しました（一部の処理で問題がありました）:\n- "
               + "\n- ".join(result["errors"]))
    return "📝 業務月報を作成しました。内容はChatworkの対象ルームに送っています。"


def _handle_monthly_report(user_id: str, text: str, msg: dict, reply_token) -> bool:
    """業務月報のLINE材料受付（TASK-20260826-002）。処理したら True（呼び出し元はそこで終了する）。

    「月報開始」〜「月報終了」の間に送った内容だけを、その回の月報の材料にする
    （通常のAI質問応答 qa.answer は経由しない。取りこぼし・雑談との混在を防ぐため）。
    """
    from services import monthly_report as MR
    from services import monthly_report_line as MRL
    from services import settings

    if settings.get_setting("monthly_report_enabled", "1") != "1":
        return False  # 機能停止中は従来どおり qa.answer 等に任せる

    session = MRL.current_session()
    if session and MRL.is_expired(session):
        # 締め忘れの放置セッション。今回のメッセージを扱う前に、そこまでの材料で自動的に締める
        # （scheduler.pyの定期チェックと同じ処理。ここでも締めるのは、次のtickを待たず
        #  「今すぐ別の話をしたい」オーナーを待たせないため）。
        result = MR.finalize_line_session(session, generated_by="line_timeout")
        line_client.push(user_id,
                         "⏰ 前回の月報の材料受付が一定時間操作が無かったため自動的に締め切り、"
                         "そこまでの材料で月報を作成しました。\n" + _monthly_report_result_text(result),
                         label="monthly_report_line_timeout")
        session = None

    cmd = MRL.parse_command(text) if msg.get("type") == "text" else None
    if cmd == "start":
        MRL.start_session(user_id)
        if reply_token:
            line_client.reply(reply_token,
                              "📥 月報の材料受付を開始しました。\n"
                              "会議の要点（テキスト）・会議資料（PDF/Excel/Word/PowerPoint等）・"
                              "画像を続けて送ってください。\n"
                              "終わったら「月報終了」と送ってください。")
        return True
    if cmd == "end":
        if not session:
            if reply_token:
                line_client.reply(reply_token,
                                  "現在受付中の月報はありません。「月報開始」から始めてください。")
            return True
        if reply_token:
            line_client.reply(reply_token, "🧠 受け付けた材料から月報を作成しています…")
        result = MR.finalize_line_session(session, generated_by="line")
        line_client.push(user_id, _monthly_report_result_text(result), label="monthly_report_line_done")
        return True
    if session:
        reply = MRL.capture(session["id"], msg)
        if reply_token:
            line_client.reply(reply_token, reply)
        else:
            line_client.push(user_id, reply, label="monthly_report_line_item")
        return True
    return False


def _handle_event(ev):
    """1つのLINEイベントを処理（別スレッドで実行）。"""
    if ev.get("type") != "message":
        return
    msg = ev.get("message", {})
    mtype = msg.get("type")
    # text＝ふつうの質問 / file＝Excel・PDF等の添付（2026-08-18対応）
    # image＝写真・スクリーンショット（claude visionで内容を読む・2026-08-25対応）
    if mtype not in ("text", "file", "image"):
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

    # ── 常駐サービスの操作（AIを通さない。誤解釈も待ち時間も無くす） ──
    if mtype == "text":
        cmd = admin_ops.parse_command(text)
        if cmd:
            op, targets = cmd
            if not _is_admin(user_id):
                if reply_token:
                    line_client.reply(reply_token, "この操作は管理者のみです。")
                return
            if op == "status":
                if reply_token:
                    line_client.reply(reply_token, admin_ops.status_text())
                _log_line(user_id, text, note="admin:status")
                return
            names = "・".join(admin_ops.LABELS[t][1] for t in targets)
            warn = "\n※LINEの通り道も再起動するので、この直後は数十秒つながりません。" \
                   if "line" in targets or "ngrok" in targets else ""
            # ★先に返信してから、切り離した別プロセスで再起動する（自分を殺しても結果は届く）
            if reply_token:
                line_client.reply(reply_token, f"再起動します:\n{names}{warn}\n\n結果は追って送ります。")
            admin_ops.restart_detached(targets, line_user_id=user_id)
            _log_line(user_id, text, note=f"admin:restart {targets}")
            return

    # ── 業務月報: LINEの材料受付（TASK-20260826-002。オーナー指示でChatwork起点を廃止し、
    #    LINEで直接送った内容だけを月報の材料・トリガーにする）──
    if _handle_monthly_report(user_id, text, msg, reply_token):
        _log_line(user_id, text, note="monthly_report_line")
        return

    # ── 添付ファイル（Excel/Word/PDF/CSV…）を読む ──
    attach_note = ""
    if mtype == "file":
        fname = msg.get("fileName") or "ファイル"
        if reply_token:
            line_client.reply(reply_token, f"「{fname}」を受け取りました。読んでいます…📄")
            reply_token = None            # reply_tokenは1回だけ。以降はpushで返す
        attach_note = attachments.read_line_file(msg.get("id"), fname)
        text = attachments.with_attachments(text, attach_note)

    # ── 画像（写真・スクリーンショット）を claude vision で読む ──
    if mtype == "image":
        if reply_token:
            line_client.reply(reply_token, "画像を受け取りました。読んでいます…🖼")
            reply_token = None            # reply_tokenは1回だけ。以降はpushで返す
        attach_note = attachments.read_line_image(msg.get("id"))
        text = attachments.with_attachments(text, attach_note)

    # ── LINEの「リプライ（引用）」を読む（2026-08-27）──
    #   利用者が写真を引用して「これは◯◯です」と言うのが一番自然な直し方なのに、
    #   `quotedMessageId` を見ていなかったため**どの写真の話か分からず**、
    #   毎回「番号で答えてください」と聞き返していた（オーナー報告）。
    #   送信時に控えたメッセージIDと突き合わせて、対象を確定して渡す。
    quoted = msg.get("quotedMessageId")
    if quoted:
        try:
            from services import image_sendlog
            hit = image_sendlog.by_line_message_id(user_id, quoted)
        except Exception:
            hit = None
        if hit:
            rid, fid, title = hit
            text += (f"\n\n（★利用者はこの発言で、あなたが送った写真を引用している。"
                     f"対象は room_id=\"{rid}\" file_id=\"{fid}\"（現在のタイトル: {title or 'なし'}）。"
                     "『これは◯◯です』のように名前を告げられたら、"
                     "番号を聞き返さずこの写真のタイトルを chatwork_image_set_title で直すこと。"
                     "『これ削除して』『間違えて投稿した』のように削除を求められたら、"
                     "番号を聞き返さずこの room_id/file_id で chatwork_image_delete を呼ぶこと。"
                     "投稿者が社員本人の場合はAPI仕様でChatwork本体からは削除できないので、"
                     "戻り値の reason/hint（手動削除の案内）を正直にそのまま伝えること）")
            _log_line(user_id, text, note=f"引用を解決: {rid}/{fid}")
        else:
            text += ("\n\n（★利用者は何かを引用して返信しているが、"
                     "こちらの記録には無い写真だった。どれを指しているか確認すること）")

    # ── claudeが既に詰まっていると分かっている場合は、呼ばずに預かる ──
    # 詰まりは全プロセス共通（Keychainのトークン）なので、2人目以降は待つだけ無駄。
    # ここで即答することで「90秒すら待たせない」（2026-08-19の障害対応・Stage 8）。
    if claude_health.is_stalled():
        _queue_and_reply(user_id, text, reply_token, first_victim=False)
        return

    # 即時ack（reply_tokenは短命・1回）。処理は続けてpushで返す。
    if reply_token:
        line_client.reply(reply_token, "受け付けました。調べています…🔎")
        reply_token = None

    try:
        res = qa.answer(text, channel="line", asker="オーナー(LINE)", line_user_id=user_id)
        answer_text = res.get("answer") or "（回答を生成できませんでした）"
    except ClaudeStalledError as e:
        # 詰まりを最初に踏んだ人。依頼は捨てずに預かり、復旧後に自動で処理する。
        _log_line(user_id, text, note=f"詰まり検知→キューへ: {e}")
        _queue_and_reply(user_id, text, reply_token, first_victim=True)
        return
    except Exception as e:
        # 詰まり以外の失敗は、**何が起きたかを本文で伝える**
        #   （従来は type(e).__name__ だけで「ClaudeError」としか出ず、原因が消えていた）
        answer_text = f"処理中にエラーが発生しました。\n{type(e).__name__}: {e}"
        _log_line(user_id, text, note=str(e))
    ok = line_client.push(user_id, answer_text, label="qa_answer")
    _log_line(user_id, text, reply_text=answer_text,
              note=None if ok else f"LINEへの送信に失敗: {line_client.last_error()}")
    if not ok:
        # 黙って消えると「質問したのに無反応」にしか見えない（2026-08-20の障害）。
        # 回答そのものはLINEの都合で送れないので、起きた事実だけChatworkへ回す。
        _alert_send_failure(user_id, text)


def _alert_send_failure(user_id: str, asked: str):
    """LINEへ回答を送れなかったことを、Chatworkの管理者ルームへ知らせる。"""
    try:
        from services import line_alert
        err = line_client.last_error() or {}
        if err.get("kind") == "quota_exhausted":
            why = ("LINEの送信可能メッセージ数（月の上限）を使い切っています。"
                   "プランを上げるか、月初のリセットをお待ちください。")
        else:
            why = f"理由: {err.get('kind')} / status={err.get('status')} {err.get('body', '')[:120]}"
        line_alert.alert(
            f"⚠️ LINEへ回答を送れませんでした。\n\n"
            f"ご質問: {asked[:150]}\n\n{why}\n\n"
            f"※お手数ですが、同じ内容をこちらのChatworkへ送っていただければ回答できます。",
            dedup_key=None)
    except Exception as e:
        print(f"[line] 失敗通知そのものに失敗: {type(e).__name__}: {e}", flush=True)


def _queue_and_reply(user_id: str, text: str, reply_token, first_victim: bool):
    """依頼を預かり、待たせない返事をする（結果は復旧後に push で届く）。"""
    pending.enqueue(text, channel="line", requester="オーナー(LINE)", line_user_id=user_id)
    n = pending.queued_count()
    if first_victim:
        head = "いま claude の認証が詰まっているようです（アプリの不具合ではありません）。"
    else:
        head = "いま claude の認証が詰まっている状態が続いています。"
    # LINEはMarkdownを解釈しないので装飾記号は使わない（** がそのまま文字として出る）
    msg = (f"⏳ {head}\n\n"
           f"ご依頼はお預かりしました。復旧しだい自動で処理して、結果をこちらへお送りします。\n"
           f"投げ直していただく必要はありません。\n\n"
           f"（お預かり中のご依頼: {n}件）")
    if reply_token:
        line_client.reply(reply_token, msg)
    else:
        line_client.push(user_id, msg, label="stalled_ack")
    _log_line(user_id, text, reply_text=msg, note="詰まり中のためキューへ預かった")


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
        elif self.path.startswith("/line/web_image/"):
            self._serve_web_image(self.path[len("/line/web_image/"):])
        else:
            self._send(404, b"not found")

    def _serve_web_image(self, token):
        """streetview_lookup等でネット取得した一時画像を、LINE画像pushのURL先として配信する
        （web_image_store.STORE_DIR配下のみ。image_tokenは英数字のみなので安全）。"""
        import mimetypes

        from services import web_image_store
        path = web_image_store.path_for(token)
        if not path:
            self._send(404, b"not found")
            return
        ctype = mimetypes.guess_type(path)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
