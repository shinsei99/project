"""TODO Tool。既存 services/tasks.py を安全にラップ。"""
from db.connection import query
from services import property_master, tasks as T
from services.agent_tools import format_tools


def _row(t):
    if not t:
        return None
    return {
        "id": t["id"], "content": t["content"], "status": t["status"],
        "assignee": t["assignee_name"], "requester": t["requester"],
        "due_date": t["due_date"], "due_raw": t["due_raw"], "priority": t["priority"],
        "progress": t["progress"], "room_id": t["room_id"],
        "project_id": t["project_id"], "source_message_id": t["source_message_id"],
        "check_count": t["check_count"], "escalation_stage": t["escalation_stage"],
        "last_check_at": t["last_check_at"], "last_progress_reply": t["last_progress_reply"],
    }


def task_search(keyword=None, assignee=None, status=None, room_id=None, only_open=False, limit=30):
    sql = "SELECT * FROM tasks WHERE 1=1"
    params = []
    if keyword:
        sql += " AND content LIKE ?"; params.append(f"%{keyword}%")
    if assignee:
        sql += " AND assignee_name LIKE ?"; params.append(f"%{assignee}%")
    if status:
        sql += " AND status=?"; params.append(status)
    if room_id:
        sql += " AND room_id=?"; params.append(room_id)
    if only_open:
        ph = ",".join("?" * len(T.OPEN_STATUSES))
        sql += f" AND status IN ({ph})"; params += T.OPEN_STATUSES
    sql += " ORDER BY (due_date IS NULL), due_date, id DESC LIMIT ?"; params.append(limit)
    rows = query(sql, tuple(params))
    tasks = [_row(r) for r in rows]
    # formatted: 担当者ごとにグループ化＋状態アイコンで整形済みの文字列（定時TODO確認と同じ見た目）。
    # 複数件を一覧で答えるときは、これをそのまま回答本文として使うこと（バラバラの箇条書きにしない）。
    return {"ok": True, "count": len(rows), "tasks": tasks,
            "formatted": format_tools.format_grouped_task_list(tasks)}


def task_create(content, assignee_name=None, assignee_account_id=None, requester=None,
                customer=None, due_date=None, due_raw=None, room_id=None,
                source_message_id=None, project_id=None, priority="中",
                done_condition=None, reason=None, confidence="高"):
    content = (content or "").strip()
    if not content:
        return {"ok": False, "error": "content が空です"}
    if not assignee_name and not assignee_account_id:
        match = property_master.find_assignee(content)
        if match:
            assignee_name = match["assignee_name"]
            note = f"物件担当マスタから自動割当（{'/'.join(match['matched_candidates'])}）"
            reason = f"{reason}／{note}" if reason else note
    # 重複防止: 同ルーム・同内容の未完了TODOがあれば流用
    dedup_key = f"{room_id}:{content}"[:200] if room_id else None
    if dedup_key:
        ex = T.find_by_dedup_key(dedup_key)
        if ex and ex["status"] in T.OPEN_STATUSES + [T.STATUS_AI_CONFIRM]:
            T.touch_activity(ex["id"], note="同内容の再依頼", evidence_message_id=source_message_id)
            return {"ok": True, "created": False, "duplicate_of": ex["id"],
                    "message": f"既存TODO #{ex['id']} と重複のため作成しませんでした", "task": _row(T.get_task(ex["id"]))}
    tid = T.create_task({
        "content": content, "assignee_name": assignee_name,
        "assignee_account_id": assignee_account_id, "requester": requester,
        "customer": customer, "due_date": due_date, "due_raw": due_raw,
        "room_id": room_id, "source_message_id": source_message_id,
        "project_id": project_id, "priority": priority or "中",
        "done_condition": done_condition, "ai_reason": reason,
        "ai_confidence": confidence, "status": T.STATUS_TODO, "dedup_key": dedup_key,
    })
    return {"ok": True, "created": True, "task_id": tid, "task": _row(T.get_task(tid))}


def task_update(task_id, due_date=None, due_raw=None, assignee_name=None,
                assignee_account_id=None, content=None, priority=None,
                project_id=None, reason=None, evidence_message_id=None):
    t = T.get_task(task_id)
    if not t:
        return {"ok": False, "error": f"task #{task_id} が見つかりません"}
    updates = {}
    for k, v in (("due_date", due_date), ("due_raw", due_raw), ("assignee_name", assignee_name),
                 ("assignee_account_id", assignee_account_id), ("content", content),
                 ("priority", priority), ("project_id", project_id)):
        if v is not None:
            updates[k] = v
    if not updates:
        return {"ok": False, "error": "更新項目がありません"}
    T.update_fields(task_id, updates, note=reason, evidence_message_id=evidence_message_id)
    return {"ok": True, "task_id": task_id, "updated": list(updates.keys()), "task": _row(T.get_task(task_id))}


def task_complete(task_id, note=None, evidence_message_id=None):
    t = T.get_task(task_id)
    if not t:
        return {"ok": False, "error": f"task #{task_id} が見つかりません"}
    T.update_status(task_id, T.STATUS_DONE, note=note or "完了", evidence_message_id=evidence_message_id, progress=100)
    return {"ok": True, "task_id": task_id, "status": T.STATUS_DONE}


def task_progress_update(task_id, status=None, note=None, progress=None, evidence_message_id=None):
    t = T.get_task(task_id)
    if not t:
        return {"ok": False, "error": f"task #{task_id} が見つかりません"}
    new_status = status or t["status"]
    if new_status not in T.ALL_STATUSES:
        return {"ok": False, "error": f"不正な状態: {new_status}（{T.ALL_STATUSES}）"}
    T.update_status(task_id, new_status, note=note, evidence_message_id=evidence_message_id, progress=progress)
    # 進捗回答を記録（担当者の返答など）
    if note:
        from db.connection import get_conn
        with get_conn() as c:
            c.execute("UPDATE tasks SET last_progress_reply=? WHERE id=?", (note[:500], task_id))
        T.mark_progress_reported(task_id)
    return {"ok": True, "task_id": task_id, "status": new_status, "task": _row(T.get_task(task_id))}
