"""LINEが使えないときに、**Chatworkで**管理者へ知らせるための口。

## なぜ要るか（2026-08-20の障害）

`worker._notify_admin()` は障害の通知を **LINEのpush** で送っていた。ところが
2026-08-20 に起きた障害は「LINEの送信可能メッセージ数(200通/月)を使い切った」
ことそのものだったため、**障害を知らせる通知も同じ理由で送れなかった**。
壊れた経路で「壊れました」と言おうとしていた、という循環になっていた。

そこで、LINEが駄目なときは Chatwork（通数無制限）へ回す。Chatworkへの投稿は
既存の outbox を通す（履歴・冪等・管理画面での可視化のため）。

kind='system_alert' は outbox.ALWAYS_SEND_KINDS に入れてあるので、post_mode が
confirm でも保留されずに届く（障害通知を人の承認待ちで止めては意味がない）。
"""
from services import outbox, settings
from services.chatwork import ChatworkClient
from db.connection import get_conn

_PREFIX = "🩺 AI業務マネージャー"


def admin_room_id():
    """障害を知らせる先の Chatwork ルームID。

    1. 設定 `manager_room_id` があればそれ
    2. 無ければ監視中のダイレクトチャット（＝オーナーとの1対1）
    3. それも無ければ None（呼び出し側は静かに諦める）
    """
    rid = settings.get_setting("manager_room_id", "") or ""
    rid = str(rid).strip()
    if rid.isdigit():
        return int(rid)
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT room_id FROM rooms WHERE type='direct' AND monitored=1 "
                "ORDER BY room_id LIMIT 1"
            ).fetchone()
        return int(row["room_id"]) if row else None
    except Exception:
        return None


def alert(text: str, dedup_key=None) -> bool:
    """管理者のChatworkへ障害を知らせる。送れたら True。

    dedup_key を渡すと同じ通知は一度しか積まれない（毎周期の連投を防ぐ）。
    """
    room_id = admin_room_id()
    if not room_id:
        print(f"[line_alert] 通知先ルームが無いため送れません: {text[:60]}", flush=True)
        return False
    try:
        ob_id = outbox.enqueue(
            room_id, f"{_PREFIX}\n\n{text}", kind="system_alert",
            reason="LINE障害・送信枠の通知", dedup_key=dedup_key,
        )
        if not ob_id:
            return False
        return bool(outbox.send_one(ChatworkClient(), ob_id).get("ok"))
    except Exception as e:
        print(f"[line_alert] Chatworkへの通知に失敗: {type(e).__name__}: {e}", flush=True)
        return False
