"""通知の共通口（開発タスクの進捗・完了・質問を、依頼が来た入口へ返す）。

LINE から来た依頼は LINE へ、Chatwork から来た依頼はそのルームへ返す。
入口ごとに別の通知処理を書かないための薄いラッパ。

Chatwork への投稿は既存の outbox を通す（履歴・冪等・管理画面での可視化のため）。
kind='dev_report' は ALWAYS_SEND_KINDS に入れてあるので、post_mode=confirm でも
「本人が頼んだ開発の報告」は保留されず届く（自発投稿ではないため）。
"""
from services import line_client, outbox
from services.chatwork import ChatworkClient, mention

_PREFIX = "🛠 開発エージェント"


def notify(task: dict, text: str, dedup_key=None) -> bool:
    """依頼元の入口へ通知する。task は dev_tasks の行（dict）。"""
    channel = (task or {}).get("channel") or "admin"
    body = f"【{task.get('task_id')}】{text}".strip()
    if channel == "line":
        user_id = task.get("line_user_id")
        if not user_id:
            return False
        return line_client.push(user_id, f"{_PREFIX}\n{body}", label="dev_notify")
    if channel == "chatwork":
        room_id = task.get("room_id")
        if not room_id:
            return False
        to = ""
        try:
            requester_id = task.get("requester_account_id")
            if requester_id:
                to = mention(int(requester_id), task.get("requester")) + "\n"
        except (TypeError, ValueError):
            to = ""
        ob_id = outbox.enqueue(
            room_id, f"{to}{_PREFIX}\n\n{body}", kind="dev_report",
            reason="開発タスクの進捗・完了報告", dedup_key=dedup_key,
        )
        if not ob_id:
            return False
        try:
            return bool(outbox.send_one(ChatworkClient(), ob_id).get("ok"))
        except Exception:
            return False
    # channel == "admin"（管理画面から作られたタスク）は画面で見るので送らない
    return False
