"""会話 → 業務抽出の中核。

ルーム単位で未解析メッセージをまとめて 1 回の claude 呼び出しに束ね、
イベント配列(JSON)を受け取って tasks / task_events を更新する。

方針（CLAUDE指示 §7,10-14,38,39,40 準拠）:
  - 「誰かが何かをする必要がある」ものだけTODO化。あいさつ・相槌はTODOにしない。
  - 確信が低い(推測/不明)ものは自動登録せず status=AI確認待ち に置く。
  - 既存TODOの更新/進捗/完了は target_task_id で紐付け、重複TODOを作らない。
  - 期限は本日基準でISO化。曖昧は null（未確定）で断定しない。
  - 判断理由(ai_reason)と確信度を必ず保存し、後から追跡できるようにする。
"""
import datetime
import json
import os

from db.connection import get_conn, query
from services import attachments, property_master, tasks as T
from services.claude_client import ClaudeError, run_json

CONTEXT_MSG_LIMIT = 15   # 会話の流れとして渡す直近メッセージ数
LOW_CONF = ("推測", "不明")


def _line_body(room_id, m, limit) -> str:
    """会話ラインに載せる本文。音声・画像添付があれば内容を足す（TASK-20260826-004 / TASK-20260827-001）。

    従来ファイル添付（Excel/PDF等）はQ&A時のみ内容を読み、TODO抽出には載せない設計だが、
    音声・画像は「文字起こし/読み取り結果もTODO抽出と同様に活用」というオーナー要望のため
    例外的に対応する（設備の型番・破損箇所・検針メーター等をTODOに反映できるように）。
    transcribe_chatwork_audio / read_chatwork_image はキャッシュ済みなら即返るので、
    直近文脈に繰り返し出てきても軽い。
    """
    body = m["body"] or ""
    text = body[:limit]
    for file_id, name in attachments.chatwork_file_refs(body):
        ext = os.path.splitext(name)[1].lower()
        if ext in attachments.AUDIO_EXTENSIONS:
            text += "\n" + attachments.transcribe_chatwork_audio(room_id, file_id, name)
        elif ext in attachments.IMAGE_EXTENSIONS:
            text += "\n" + attachments.read_chatwork_image(
                room_id, file_id, name, message_id=m["message_id"])
    return text


def _today_str() -> str:
    now = datetime.datetime.now()
    wd = ["月", "火", "水", "木", "金", "土", "日"][now.weekday()]
    return f"{now.strftime('%Y-%m-%d')}（{wd}）"


def _unprocessed(room_id: int, ai_account_id):
    """未解析メッセージ。自分(AI)の投稿は解析対象外（ただし processed にはする）。"""
    rows = query(
        "SELECT * FROM messages WHERE room_id=? AND processed=0 ORDER BY send_time, message_id",
        (room_id,),
    )
    targets, self_ids = [], []
    for r in rows:
        if ai_account_id is not None and r["account_id"] == ai_account_id:
            self_ids.append(r["message_id"])
        else:
            targets.append(r)
    return targets, self_ids


def _recent_context(room_id: int):
    rows = query(
        "SELECT * FROM messages WHERE room_id=? ORDER BY send_time DESC, message_id DESC LIMIT ?",
        (room_id, CONTEXT_MSG_LIMIT),
    )
    return list(reversed(rows))


def _members(room_id: int):
    return query("SELECT account_id, name FROM members WHERE room_id=?", (room_id,))


def _build_prompt(room_id, new_msgs, context_msgs, members, open_tasks) -> str:
    member_lines = "\n".join(
        f"  - {m['name']}（account_id={m['account_id']}）" for m in members
    ) or "  （不明）"
    ctx_lines = "\n".join(
        f"  [{m['message_id']}] {m['account_name'] or m['account_id']}: {_line_body(room_id, m, 300)}"
        for m in context_msgs
    ) or "  （なし）"
    new_lines = "\n".join(
        f"  [{m['message_id']}] {m['account_name'] or m['account_id']}: {_line_body(room_id, m, 600)}"
        for m in new_msgs
    )
    if open_tasks:
        task_lines = "\n".join(
            f"  - task_id={t['id']} / {t['content']} / 担当={t['assignee_name'] or '?'} "
            f"/ 状態={t['status']} / 期限={t['due_date'] or '未確定'}"
            for t in open_tasks
        )
    else:
        task_lines = "  （このルームに未完了TODOなし）"

    return f"""あなたは日本の不動産会社の「AI業務マネージャー」です。社内Chatworkの会話を読み、業務(TODO)を抽出・更新します。

# 本日
{_today_str()}

# このルームのメンバー
{member_lines}

# 会話の流れ（参考・判定対象ではない）
{ctx_lines}

# 既存の未完了TODO（重複を作らないため。更新・進捗・完了はこのidに紐付ける）
{task_lines}

# 今回判定する新着メッセージ
{new_lines}

# あなたのタスク
新着メッセージそれぞれについて、業務上の意味を判定し「イベント」の配列を JSON で返してください。

## event_type の種類
- "new_task": 新しくTODO化すべき仕事の依頼・宣言（誰かが何かをする必要がある）
- "progress_update": 既存TODOの進捗（着手/進行中/確認待ち等）。target_task_id 必須
- "completion": 既存TODOの完了・完了報告。target_task_id 必須
- "due_change": 既存TODOの期限変更。target_task_id 必須
- "question_to_ai": AI(あなた)への質問・@Claude 宛の問いかけ
- "none": 業務ではない（あいさつ・相槌・雑談・「了解です」「ありがとうございます」等）

## 重要ルール
1. すべての発言をTODOにしない。「誰かが何かをする必要がある」ものだけ new_task にする。
2. 依頼か雑談か自信が持てない時は confidence を "推測" か "不明" にする（勝手に確定登録しない）。
3. 既存TODOに関する進捗・完了・期限変更は new_task を作らず、target_task_id で該当TODOに紐付ける。
4. 期限は本日を基準に "YYYY-MM-DD" へ変換（明日/金曜/来週/月末等）。判断できなければ due_date=null、元表現を due_raw に残す。
5. 担当者は会話とメンバーから推定し、可能なら assignee_account_id も埋める。不明なら null。
6. reason には「なぜそう判断したか」を日本語で簡潔に必ず書く。
7. **1つのメッセージに、複数の独立した物件・案件についての業務報告（完了・進行中など）が
   まとめて書かれることがある**（例:「A邸図面作成完了、B社契約手続き進行中、C物件引渡し完了」）。
   このとき、まとめて1件のイベントにせず、**案件ごとに別々のイベントへ分割する**こと。
   同じ message_id を複数のイベントで使ってよい（1メッセージ→複数イベントは正常）。
8. 分割した案件ごとの報告が、既存の未完了TODO（一覧参照）のどれにも該当しない場合
   （＝そもそもTODOとして事前登録されていなかった業務についての完了・進行中の報告）は、
   target_task_id が見つからないからと黙って捨てない。new_task として登録し、
   task.report_status に実際の状態を入れること:
   - 既に完了済みの報告 → "完了"
   - 着手済み・進行中の報告 → "進行中"
   - まだ着手していない依頼 → "未着手"（省略時のデフォルト）
   （「業務記録を入力してください」のような、特定の案件を指さない**汎用の依頼TODO**への
   返信として複数件の案件が報告された場合も同様。汎用TODO自体への completion イベントは
   従来通り target_task_id で送りつつ、報告された案件ごとに上記の new_task を追加で出す。
   汎用TODOの完了1件だけで案件6件分の報告を済ませたことにしない。）

## 出力フォーマット（JSON配列のみ。前後に説明文を書かない）
[
  {{
    "message_id": "対象メッセージのID(文字列)",
    "event_type": "new_task|progress_update|completion|due_change|question_to_ai|none",
    "target_task_id": null,
    "confidence": "明示|高|推測|不明",
    "is_speculative": false,
    "new_status": null,
    "reason": "判断理由",
    "task": {{
      "content": "TODOの内容（new_task/due_changeの時）",
      "assignee_name": null,
      "assignee_account_id": null,
      "requester": null,
      "customer": null,
      "project": null,
      "due_date": null,
      "due_raw": null,
      "done_condition": null,
      "priority": "中",
      "report_status": "未着手",
      "conf_assignee": "明示|高|推測|不明",
      "conf_due": "明示|高|推測|不明",
      "conf_done": "明示|高|推測|不明",
      "conf_project": "明示|高|推測|不明"
    }}
  }}
]
new_task/due_change 以外では "task" は省略可（null）でよい。
report_status は new_task の時だけ使う（"未着手"|"進行中"|"完了"。ルール8参照）。"""


def _norm_name(s):
    return str(s or "").replace(" ", "").replace("　", "")


def _apply_property_master(content, reason):
    """担当者が未確定のTODOに、物件×担当者マスタ（properties.assignee_name）から
    物件名を突き合わせて担当者を補う（TASK-20260826-003）。一致しなければ何もしない。"""
    match = property_master.find_assignee(content)
    if not match:
        return None, reason
    note = f"物件担当マスタから自動割当（{'/'.join(match['matched_candidates'])}）"
    reason = f"{reason}／{note}" if reason else note
    return match["assignee_name"], reason


def _global_member_lookup(name):
    """全ルーム横断で氏名→account_id を引く（該当ルームの members 同期がまだ実行されていない/
    そのルームでは未確認のメンバーの場合のフォールバック）。
    社内は少人数で氏名がほぼユニークなため、同姓同名の衝突は考慮しない。"""
    norm = _norm_name(name)
    if not norm:
        return None
    rows = query("SELECT account_id, name FROM members WHERE name IS NOT NULL ORDER BY updated_at DESC")
    for m in rows:
        if _norm_name(m["name"]) == norm:
            return m["account_id"]
    return None


def _resolve_account_id(members, name, given_id):
    if given_id:
        return given_id
    if not name:
        return None
    norm = _norm_name(name)
    for m in members:
        if m["name"] and _norm_name(m["name"]) == norm:
            return m["account_id"]
    # このルームの members 同期がまだ/欠落している場合、全ルーム横断の既知メンバーで再解決を試みる
    return _global_member_lookup(name)


def _apply_events(room_id, events, members, msg_by_id):
    created, updated = 0, 0
    for ev in events:
        etype = ev.get("event_type")
        mid = str(ev.get("message_id")) if ev.get("message_id") is not None else None
        reason = ev.get("reason")
        conf = ev.get("confidence")
        target = ev.get("target_task_id")

        if etype == "new_task":
            task = ev.get("task") or {}
            content = (task.get("content") or "").strip()
            if not content:
                continue
            aid = _resolve_account_id(members, task.get("assignee_name"), task.get("assignee_account_id"))
            assignee_name = task.get("assignee_name")
            if not assignee_name and not aid:
                assignee_name, reason = _apply_property_master(content, reason)
            # report_status: 事前登録の無かった案件を「完了/進行中の報告」として登録する場合の初期状態
            # （ルール8）。confidenceが低い時は従来通りAI確認待ちを優先する。
            report_status = task.get("report_status")
            if report_status not in (T.STATUS_TODO, T.STATUS_DOING, T.STATUS_DONE):
                report_status = T.STATUS_TODO
            status = T.STATUS_AI_CONFIRM if conf in LOW_CONF else report_status
            dedup_key = f"{room_id}:{content}"[:200]
            # 同一 dedup_key の未完了TODOが既にあればスキップ（多重生成防止）
            existing = T.find_by_dedup_key(dedup_key)
            if existing and existing["status"] in T.OPEN_STATUSES + [T.STATUS_AI_CONFIRM]:
                T.touch_activity(existing["id"], note="同内容の再言及", evidence_message_id=mid)
                continue
            T.create_task({
                "content": content,
                "assignee_name": assignee_name,
                "assignee_account_id": aid,
                "requester": task.get("requester"),
                "customer": task.get("customer"),
                "due_date": task.get("due_date"),
                "due_raw": task.get("due_raw"),
                "done_condition": task.get("done_condition"),
                "priority": task.get("priority") or "中",
                "status": status,
                "room_id": room_id,
                "source_message_id": mid,
                "ai_reason": reason,
                "ai_confidence": conf,
                "conf_assignee": task.get("conf_assignee"),
                "conf_due": task.get("conf_due"),
                "conf_done": task.get("conf_done"),
                "conf_project": task.get("conf_project"),
                "is_speculative": 1 if ev.get("is_speculative") else 0,
                "dedup_key": dedup_key,
            })
            created += 1

        elif etype in ("progress_update", "completion", "due_change"):
            t = T.get_task(target) if target else None
            if not t:
                # target_task_id が無い/存在しない = どのTODOのことか特定できなかった。
                # 従来はここで無言で continue しており、進捗報告そのものがDBに一切残らず消えていた
                # （2026-08-19 TASK-20260819-002 の実害）。人が「⏰ 定時処理ログ」画面の
                # notifications で拾えるよう必ず記録する（推測でどれかのTODOに紐付けはしない）。
                src = dict(msg_by_id[mid]) if mid and mid in msg_by_id else {}
                with get_conn() as conn:
                    conn.execute(
                        "INSERT INTO notifications (type, room_id, payload) VALUES ('unresolved_task_link', ?, ?)",
                        (room_id, json.dumps({
                            "message_id": mid, "event_type": etype, "target_task_id": target,
                            "reason": reason, "text": src.get("body"),
                        }, ensure_ascii=False)),
                    )
                continue
            if etype == "completion":
                new_status = ev.get("new_status") or T.STATUS_WAITING  # 完了候補は既定で確認待ち
                T.update_status(target, new_status, note=reason, evidence_message_id=mid)
                T.mark_progress_reported(target)
            elif etype == "progress_update":
                new_status = ev.get("new_status") or T.STATUS_DOING
                T.update_status(target, new_status, note=reason, evidence_message_id=mid)
                T.mark_progress_reported(target)
            elif etype == "due_change":
                task = ev.get("task") or {}
                T.update_fields(target, {"due_date": task.get("due_date"), "due_raw": task.get("due_raw")},
                                note=reason, evidence_message_id=mid)
            updated += 1

        elif etype == "question_to_ai":
            # M1 では検出・記録のみ（回答は M3 の qa.py で実装）
            with get_conn() as conn:
                conn.execute(
                    "INSERT INTO notifications (type, room_id, payload) VALUES ('question', ?, ?)",
                    (room_id, json.dumps({"message_id": mid, "reason": reason}, ensure_ascii=False)),
                )
        # "none" は何もしない
    return created, updated


def _log_analysis(room_id, msg_ids, prompt, env, parsed, error=None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ai_analysis_logs (room_id, kind, message_ids, model, prompt, raw_output, parsed, error, duration_ms) "
            "VALUES (?, 'extract', ?, 'sonnet', ?, ?, ?, ?, ?)",
            (room_id, json.dumps([str(m) for m in msg_ids], ensure_ascii=False), prompt,
             (env or {}).get("result") if env else None,
             json.dumps(parsed, ensure_ascii=False) if parsed is not None else None,
             error, (env or {}).get("_elapsed_ms") if env else None),
        )


def _mark_processed(message_ids):
    if not message_ids:
        return
    with get_conn() as conn:
        conn.executemany(
            "UPDATE messages SET processed=1 WHERE message_id=?",
            [(mid,) for mid in message_ids],
        )


def analyze_room(room_id: int, ai_account_id=None) -> dict:
    """1 ルーム分の未解析メッセージを解析し、結果サマリを返す。"""
    new_msgs, self_ids = _unprocessed(room_id, ai_account_id)
    _mark_processed(self_ids)   # 自分の投稿は解析せず既読化
    if not new_msgs:
        return {"room_id": room_id, "analyzed": 0, "created": 0, "updated": 0}

    members = _members(room_id)
    context_msgs = _recent_context(room_id)
    open_tasks = T.open_tasks_in_room(room_id, include_ai_confirm=True)
    msg_by_id = {m["message_id"]: m for m in new_msgs}
    prompt = _build_prompt(room_id, new_msgs, context_msgs, members, open_tasks)
    new_ids = [m["message_id"] for m in new_msgs]

    try:
        from services import settings
        parsed, env = run_json(prompt, model=settings.get_setting("model_analyzer", "haiku"), timeout=300)
        if not isinstance(parsed, list):
            parsed = parsed.get("events", []) if isinstance(parsed, dict) else []
    except ClaudeError as e:
        # 失敗時はメッセージを未処理のまま残し、次回リトライ（ログは残す）
        _log_analysis(room_id, new_ids, prompt, None, None, error=str(e))
        return {"room_id": room_id, "analyzed": 0, "created": 0, "updated": 0, "error": str(e)}

    created, updated = _apply_events(room_id, parsed, members, msg_by_id)
    _log_analysis(room_id, new_ids, prompt, env, parsed)
    _mark_processed(new_ids)
    return {"room_id": room_id, "analyzed": len(new_ids), "created": created, "updated": updated}
