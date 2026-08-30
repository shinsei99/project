"""Project Tool。既存 services/projects.py を再利用。"""
from services import projects as P
from services import company_scope as CS


def _p(row):
    return {"id": row["id"], "name": row["name"], "customer": row["customer"],
            "status": row["status"], "room_id": row["room_id"]}


def project_search(keyword=None, limit=30):
    if not CS.is_default_company():
        return CS.deny(what="案件")
    rows = P.search(keyword, limit=limit)
    out = []
    for r in rows:
        d = _p(r)
        tasks = P.tasks_of(r["id"])
        d["open_tasks"] = [
            {"id": t["id"], "content": t["content"], "status": t["status"],
             "assignee": t["assignee_name"], "due_date": t["due_date"]}
            for t in tasks if t["status"] not in ("完了", "キャンセル")
        ]
        out.append(d)
    return {"ok": True, "count": len(out), "projects": out}


def project_update(project_id, name=None, customer=None, status=None, room_id=None, reason=None):
    if not CS.is_default_company() or CS.blocks_room(room_id):
        return CS.deny(room_id, "案件")
    updates = {}
    for k, v in (("name", name), ("customer", customer), ("status", status), ("room_id", room_id)):
        if v is not None:
            updates[k] = v
    if not updates:
        return {"ok": False, "error": "更新項目がありません"}
    ok = P.update(project_id, updates, note=reason)
    if not ok:
        return {"ok": False, "error": f"project #{project_id} を更新できませんでした"}
    return {"ok": True, "project_id": project_id, "updated": list(updates.keys())}
