#!/usr/bin/env python3
"""常時起動デーモン: ポーリング → 解析（→ M2以降で監督・スケジューラ）。

使い方:
  python3 worker.py                 # 常時ループ
  python3 worker.py --once          # 1 サイクルだけ実行して終了（テスト用）
  python3 worker.py --whoami        # トークン所有者(=AIアカウント)を表示
  python3 worker.py --list-rooms    # 参加ルーム一覧（同期して表示）
  python3 worker.py --monitor ID    # ルームを監視対象に
  python3 worker.py --unmonitor ID  # 監視対象から外す

launchd では引数なし（常時ループ）で起動する。/usr/bin/python3 を使うこと。
"""
import argparse
import atexit
import fcntl
import os
import sys
import time

sys.path.insert(0, __import__("os").path.dirname(__import__("os").path.abspath(__file__)))

from db.connection import get_conn, query  # noqa: E402
from db.migrate import migrate  # noqa: E402
from services import settings, sync  # noqa: E402
from services.chatwork import ChatworkClient  # noqa: E402

_LOCK_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "worker.lock")
_lock_fh = None


def _acquire_singleton_lock():
    """flock で常時ループの多重起動を構造的に防ぐ。取得できなければ即終了。"""
    global _lock_fh
    os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
    _lock_fh = open(_LOCK_PATH, "w")
    try:
        fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[worker] 既に別のworkerが稼働中です（多重起動防止）。終了します。", flush=True)
        sys.exit(0)
    _lock_fh.write(str(os.getpid()))
    _lock_fh.flush()
    atexit.register(_release_lock)


def _release_lock():
    global _lock_fh
    if _lock_fh:
        try:
            fcntl.flock(_lock_fh.fileno(), fcntl.LOCK_UN)
            _lock_fh.close()
        except Exception:
            pass


def cmd_whoami():
    client = ChatworkClient()
    me = client.get_me()
    print(f"account_id={me.get('account_id')}  name={me.get('name')}  "
          f"chatwork_id={me.get('chatwork_id')}")


def cmd_list_rooms():
    client = ChatworkClient()
    n = sync.sync_rooms(client)
    print(f"synced {n} rooms:")
    for r in query("SELECT room_id, name, type, monitored FROM rooms ORDER BY monitored DESC, room_id"):
        flag = "★監視" if r["monitored"] else "   "
        print(f"  {flag}  {r['room_id']}  [{r['type']}]  {r['name']}")


def _set_monitor(room_id: int, on: bool):
    client = ChatworkClient()
    sync.sync_rooms(client)          # 名前を最新化
    with get_conn() as conn:
        conn.execute("UPDATE rooms SET monitored=? WHERE room_id=?", (1 if on else 0, room_id))
    if on:
        sync.sync_members(client, room_id)
    print(f"room {room_id} monitored={'ON' if on else 'OFF'}")


def run_forever():
    _acquire_singleton_lock()   # 多重起動防止（2つ目以降は即終了）
    migrate()
    client = ChatworkClient()
    ai_id = sync.get_ai_account_id(client)
    name = settings.get_state("ai_account_name", "")
    # クラッシュ復旧: 前回中断された'processing'を'pending'へ戻す（再起動耐性・Stage4）
    _recover_processing()
    print(f"[worker] start. AIアカウント: {name}(account_id={ai_id})", flush=True)
    from services import dev_runner, scheduler
    # 開発タスクの再起動復元（中断された実行を実行待ちへ戻す。回答待ちはそのまま）
    try:
        restored = dev_runner.recover()
        if restored:
            print(f"[worker] 開発タスク復元: {restored}", flush=True)
    except Exception as e:
        print(f"[worker] dev recover error: {type(e).__name__}: {e}", flush=True)
    while True:
        interval = settings.get_int("poll_interval_sec", 90)
        try:
            summary = sync.run_cycle(client, ai_id)
            if summary["polled"] or summary["created"] or summary["updated"] or summary.get("answered"):
                print(f"[worker] cycle {summary}", flush=True)
        except Exception as e:
            print(f"[worker] cycle error: {type(e).__name__}: {e}", flush=True)
        # 定時処理（13:00/18:00/翌10:00）。scheduled_runsで二重実行を防止。
        try:
            ran = scheduler.tick(client)
            for r in ran:
                if r.get("claimed"):
                    print(f"[worker] scheduled {r}", flush=True)
        except Exception as e:
            print(f"[worker] scheduler error: {type(e).__name__}: {e}", flush=True)
        # 開発タスク（DEVELOPMENT Agent）。実行は別スレッド・同時1本。ループは止めない。
        try:
            r = dev_runner.tick()
            if r.get("started") or r.get("gave_up"):
                print(f"[worker] dev {r}", flush=True)
        except Exception as e:
            print(f"[worker] dev error: {type(e).__name__}: {e}", flush=True)
        # claudeの詰まり監視と、預かった依頼の消化（Stage 8・2026-08-19の障害対応）
        try:
            _health_and_pending()
        except Exception as e:
            print(f"[worker] health error: {type(e).__name__}: {e}", flush=True)
        # LINEの送信枠の見張り（Stage 9・2026-08-20の障害対応）。1日1回だけ問い合わせる。
        try:
            _watch_line_quota()
        except Exception as e:
            print(f"[worker] line quota error: {type(e).__name__}: {e}", flush=True)
        time.sleep(interval)


# 残りがこれを下回ったらChatworkで予告する（ライトプラン5,000通に対して1割）
LINE_QUOTA_WARN_RATIO = 0.1
LINE_QUOTA_CHECKED_DATE = "line_quota_checked_date"


def _watch_line_quota():
    """LINEの送信可能メッセージ数を1日1回見て、少なくなったらChatworkで知らせる。

    ライトプラン(5,000通/月)は**追加メッセージを課金できない**ので、使い切ると
    その月はもう push が届かない。無言で止まる前に人へ渡すのが目的。
    枠のリセットは月初なので、日付が変わったときだけ問い合わせる（API消費を抑える）。
    """
    import datetime
    from services import line_client, settings as st

    today = datetime.date.today().isoformat()
    if st.get_state(LINE_QUOTA_CHECKED_DATE, "") == today:
        return
    q = line_client.quota()
    st.set_state(LINE_QUOTA_CHECKED_DATE, today)
    limit, used, remaining = q.get("limit"), q.get("used"), q.get("remaining")
    if q.get("type") != "limited" or not isinstance(remaining, int):
        # 無制限プラン、または取得できなかった。前者は見張る必要がない。
        print(f"[worker] line quota: {q}", flush=True)
        return
    print(f"[worker] line quota: 残り{remaining}通 / {limit}通（消費{used}）", flush=True)
    if remaining <= 0:
        _notify_admin(
            f"⚠️ LINEの送信可能メッセージ数を使い切りました（{used}/{limit}通）。\n"
            f"AIの回答はLINEへ届きません（受付の返信だけは無料枠外なので届きます）。\n"
            f"LINE Official Account Manager でプランを上げるか、月初のリセットをお待ちください。",
            dedup_key=f"line-quota-out-{today[:7]}")
    elif remaining <= max(1, int(limit * LINE_QUOTA_WARN_RATIO)):
        _notify_admin(
            f"⚠️ LINEの送信可能メッセージ数が残り{remaining}通です（{used}/{limit}通を消費）。\n"
            f"使い切るとAIの回答がLINEへ届かなくなります。",
            dedup_key=f"line-quota-low-{today[:7]}")


def _health_and_pending():
    """claudeが詰まっていれば復旧を待ち、復旧したら預かった依頼を流す。

    正常時はほぼ何もしない（`claude_health.tick()` は詰まっているときだけ probe する）。
    """
    from services import claude_health, pending
    was_stalled = claude_health.is_stalled()
    if was_stalled:
        _notify_admin_once()
    r = claude_health.tick()
    if r.get("recovered"):
        n = pending.queued_count()
        print(f"[worker] claude 復旧。預かり {n} 件を処理します。", flush=True)
        _notify_admin(f"✅ claude が復旧しました。\nお預かりしていた {n} 件を"
                      f"これから順に処理してお送りします。" if n else
                      "✅ claude が復旧しました。（お預かり中の依頼はありません）")
    if not claude_health.is_stalled():
        d = pending.drain()
        if d:
            print(f"[worker] pending {d}", flush=True)


def _notify_admin_once():
    """詰まりを検知したことを1回だけ知らせる（毎周送らない）。"""
    from services import claude_health, settings as st
    if st.get_state(claude_health.STALL_NOTIFIED, "0") == "1":
        return
    st.set_state(claude_health.STALL_NOTIFIED, "1")
    from services import pending
    _notify_admin(
        f"⚠️ claude の認証・接続が詰まっています（{claude_health.stalled_since()} から）。\n"
        f"アプリの不具合ではなく、claude 側のトークン更新が固まっている状態です。\n"
        f"復旧を1分ごとに確認しており、直りしだいお預かり分を自動で処理します。\n\n"
        f"お預かり中: {pending.queued_count()}件\n"
        f"理由: {claude_health.reason()}")


def _notify_admin(text: str, dedup_key=None):
    """管理者へ知らせる。LINEを試し、**送れなければChatworkへ回す**。

    2026-08-20の障害では「LINEの送信枠を使い切った」ことが障害の中身だったため、
    LINEだけに知らせる作りでは通知そのものが届かなかった（壊れた経路で壊れたことを
    伝えようとしていた）。Chatworkは通数無制限なので、こちらを最後の砦にする。
    """
    delivered = False
    try:
        from services import config, line_client
        raw = config.get("line_admin_user_ids", "") or ""
        ids = [u.strip() for u in str(raw).split(",") if u.strip()]
        if not ids:
            ids = sorted(line_client.allowed_user_ids())
        for uid in ids:
            if line_client.push(uid, f"🩺 AI業務マネージャー\n\n{text}", label="admin_notify"):
                delivered = True
        if not delivered and ids:
            err = line_client.last_error() or {}
            reason = err.get("kind") or "不明"
            text = f"{text}\n\n（LINEへ送れなかったためChatworkへ回しました。理由: {reason}）"
    except Exception as e:
        print(f"[worker] notify error: {type(e).__name__}: {e}", flush=True)
    if delivered:
        return
    try:
        from services import line_alert
        line_alert.alert(text, dedup_key=dedup_key)
    except Exception as e:
        print(f"[worker] chatwork fallback error: {type(e).__name__}: {e}", flush=True)


def _recover_processing():
    """再起動時、中断された message.process_status='processing' を 'pending' に戻す。"""
    from db.connection import get_conn
    try:
        with get_conn() as conn:
            conn.execute("UPDATE messages SET process_status='pending' WHERE process_status='processing'")
    except Exception:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--whoami", action="store_true")
    ap.add_argument("--list-rooms", action="store_true")
    ap.add_argument("--monitor", type=int)
    ap.add_argument("--unmonitor", type=int)
    args = ap.parse_args()

    migrate()
    if args.whoami:
        return cmd_whoami()
    if args.list_rooms:
        return cmd_list_rooms()
    if args.monitor:
        return _set_monitor(args.monitor, True)
    if args.unmonitor:
        return _set_monitor(args.unmonitor, False)
    if args.once:
        client = ChatworkClient()
        ai_id = sync.get_ai_account_id(client)
        summary = sync.run_cycle(client, ai_id)
        print(f"[once] {summary}")
        return
    run_forever()


if __name__ == "__main__":
    main()
