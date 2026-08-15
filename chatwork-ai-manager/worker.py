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
    from services import scheduler
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
        time.sleep(interval)


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
