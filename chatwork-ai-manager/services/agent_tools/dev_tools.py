"""開発タスク（DEVELOPMENT Agent）のTool。

司令塔である既存Agent（qa）が「これは業務ではなく開発だ」と判断したときに使う。
実装そのものはここではやらない。**受け付けてDBに積むだけ**で即座に返す
（開発は数分〜数十分かかるため、Chatwork/LINEの応答を待たせない）。
実行は worker のループが拾って行い、進捗と結果は依頼元の入口へ通知される。

依頼元（channel / room_id / LINEのuserId / 依頼者）は、親プロセスが渡す環境変数から取る。
プロンプトに個人の識別子を書かせないため（§37 秘密情報を出力しない）。
"""
import os

from services import dev_tasks as DT
from services import settings


def _origin() -> dict:
    """親（qa.answer）が env で渡した「依頼の入口」情報。"""
    def _int(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return {
        "channel": os.environ.get("CWAI_CHANNEL") or "admin",
        "room_id": _int(os.environ.get("CWAI_ROOM_ID")),
        "line_user_id": os.environ.get("CWAI_LINE_USER_ID") or None,
        "requester": os.environ.get("CWAI_REQUESTER") or None,
        "requester_account_id": _int(os.environ.get("CWAI_REQUESTER_ACCOUNT_ID")),
    }


def _allowed(origin: dict) -> (bool, str):
    """誰が開発を依頼してよいか。社員が勝手にコードを書かせないための制限。"""
    channel = origin.get("channel")
    if channel in ("admin", "line"):
        # LINEは webhook 側で userId 許可制を通過済み（オーナー本人）
        return True, ""
    if channel == "chatwork":
        raw = settings.get_setting("dev_allowed_account_ids", "") or ""
        allow = {a.strip() for a in str(raw).split(",") if a.strip()}
        aid = origin.get("requester_account_id")
        if aid is not None and str(aid) in allow:
            return True, ""
        return False, ("このChatworkアカウントからはアプリ開発の依頼を受け付けていません"
                       "（管理者のみ。管理画面「システム設定」の dev_allowed_account_ids で変更）")
    return False, "開発タスクを作成できない入口です"


def dev_task_create(request: str, title=None, kind=None, project_dir=None):
    """アプリ開発・改修の依頼を受け付ける（実装は裏で走る）。

    ★title と request はそのまま依頼者への通知に出る（services/dev_runner._start_text）。
      「いきなり開発が始まった」と見えないよう、**経緯が読み取れる書き方**にすること。

      title   … 何を直すかを1行で。例:
                「新誠の資料をパス指定で読めない（kb_read_document が大京固定）」
      request … **なぜ始まったのか**から書く。依頼者の言葉ではなく、起きたことを書く。
                悪い例: 「knowledge_tools.py を修正してください」
                良い例: 「鷲見さんから送られた財務書類を読もうとしたら『別の会社のもの』
                         と拒否された。新誠の資料ルートは company_source_dirs に
                         登録済みなのに kb_read_document だけが大京のDropbox決め打ち
                         だったため。会社ごとのルートに切り替える」

      ★自分が詰まって自分で直すときは、とくに「何をしようとして、どう詰まったか」を書く。
        依頼者から見ると、頼んでいない開発が突然始まったように見えるため。
    """
    origin = _origin()
    ok, why = _allowed(origin)
    if not ok:
        return {"ok": False, "error": why}
    workspace = settings.get_setting("dev_workspace", "/Users/apple")
    if project_dir and not os.path.isabs(project_dir):
        project_dir = os.path.join(workspace, project_dir)
    try:
        t = DT.create(request=request, title=title, kind=kind, project_dir=project_dir,
                      workspace=workspace, **origin)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {
        "ok": True, "task_id": t["task_id"], "status": t["status"],
        "message": (f"開発タスク {t['task_id']} を受け付けました。"
                    "順番に実行し、進捗と完了はこの入口に通知します。"),
    }


def dev_task_status(task_id: str):
    """開発タスク1件の状態を見る。"""
    t = DT.get(task_id)
    if not t:
        return {"ok": False, "error": f"開発タスクが見つかりません: {task_id}"}
    return {"ok": True, "task": {
        k: t.get(k) for k in ("task_id", "title", "kind", "status", "project_dir",
                              "question", "result", "error", "attempts",
                              "created_at", "updated_at")
    }, "events": DT.events(task_id, limit=10)}


def dev_task_list(status=None, limit=10):
    """開発タスクの一覧（既定は新しい順10件）。status で絞り込み可。"""
    rows = DT.list_tasks(status=status, limit=int(limit))
    return {"ok": True, "count": len(rows), "tasks": [
        {k: r.get(k) for k in ("task_id", "title", "status", "project_dir", "updated_at")}
        for r in rows
    ]}


def dev_task_answer(task_id: str, answer: str):
    """開発エージェントからの質問（WAITING_USER）にユーザーの回答を渡し、続きを再開させる。"""
    try:
        t = DT.answer(task_id, answer)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "task_id": t["task_id"], "status": t["status"],
            "message": f"{t['task_id']} を再開します。"}


def dev_task_cancel(task_id: str, reason=None):
    """開発タスクを中止する。"""
    try:
        t = DT.cancel(task_id, reason)
    except ValueError as e:
        return {"ok": False, "error": str(e)}
    return {"ok": True, "task_id": t["task_id"], "status": t["status"]}


def dev_task_progress(task_id: str, phase=None, note=None, project_dir=None, kind=None):
    """【開発エージェント専用】自分の進捗を記録する。phase: PLANNING/RUNNING/TESTING。"""
    t = DT.get(task_id)
    if not t:
        return {"ok": False, "error": f"開発タスクが見つかりません: {task_id}"}
    fields = {}
    if project_dir:
        fields["project_dir"] = project_dir
    if kind in DT.KINDS:
        fields["kind"] = kind
    if phase in (DT.PLANNING, DT.RUNNING, DT.TESTING):
        DT.set_status(task_id, phase, note=note or phase, **fields)
    else:
        if fields:
            DT.set_status(task_id, t["status"], note=note or "情報更新", **fields)
        if note:
            DT.add_event(task_id, "note", note)
    return {"ok": True, "task_id": task_id, "status": DT.get(task_id)["status"]}
