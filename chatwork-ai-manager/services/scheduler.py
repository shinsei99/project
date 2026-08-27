"""定時進捗確認（Stage 3）。worker の常時ループから tick(client) が呼ばれる。

2段階（役割を分ける。2026-08-18: 13:00のprogress_1300は廃止し1日2回に変更）:
  closing_1800  (18:00) 終業前確認     … 本日期限の未完了・未着手・停滞・完了報告なしに加え、
                                         期限未設定のTODO全件も対象に進捗を確認
  carryover_1000(翌10:30) 前日未完了   … 前日以前が期限のまま未完了＝期限超過に加え、
                                         期限未設定かつ未確認（AI確認待ち）も対象に確認・エスカレーション
  due_reminder  (既定10:30・carryover_1000と同時刻) 期限リマインド … 期限日の前日に事前リマインド。
                                         前日が休業日の場合は前倒しせず当日この時刻に送る（TASK-20260824-001）

週次棚卸し（絞り込みなしで未完了TODO全件を報告。上記の日次催促とは別物）:
  weekly_report_fri (金曜18:00) / weekly_report_mon (月曜10:30)

closing_1800 にはさらに、業務記録リマインド（Stage 16・TASK-20260827-006）を同居させている:
  その日、本人がChatworkに投稿した発言数（services/daily_report.own_message_count。18:30に
  自動生成する業務日報が実際に使っている「本人の発言」の数え方をそのまま流用＝二重管理にしない）が
  既定3件未満の社員へ、18:30の自動生成より前に「本日の業務内容を入力・報告してください」と
  個別に知らせる。TODO確認（Claudeの優先度判断）とは別の、単純な閾値判定（Pythonで完結）。
  設定 daily_record_reminder_enabled（既定1）/ daily_record_min_count（既定3）。

方針:
  - **会社の休業日（年間休暇スケジュールのオレンジ）は投稿する定時ジョブを全て止める**（オーナー指示 2026-08-22）。
    carryover/closing/due_reminder/週次棚卸し/業務日報が対象。claim だけして「休業日」と記録し、その日は再試行しない。
    ナレッジ増分リフレッシュは投稿しないので休業日も動かす。休み中に期限を過ぎたTODOは翌営業日の
    carryover_1000（期限超過）で拾われるため、取りこぼしにはならない。
  - due_reminder の対象抽出（progress_tools.tasks_needing_attention(kind="due_reminder")）自体にも
    休業日ロジックがある: 通常は「期限日の前日」を対象にするが、前日が休業日だったTODOは
    「当日」を対象に含める（前倒しで遡らず、休業日をまたいで当日に送る）。今日自体が休業日なら
    上記の全ジョブ停止により、その判定より前に丸ごとスキップされる。
  - scheduled_runs(UNIQUE run_date,job_type) を INSERT OR IGNORE で「claim」し、取れた時だけ実行 → 二重実行防止。
  - 対象TODOは progress_tools で機械抽出 → Claude(run_json)が「誰に何を送るか」を優先度判断（全員機械催促しない）。
    ただし due_reminder は「事前リマインド」なので原則全件送る（プロンプトで指示）。
  - 同じTODOを短時間に何度も催促しない（本日既に確認済みはスキップ）。
  - 段階的エスカレーション（escalation_stage）。超過を繰り返す場合は依頼者/管理者へ報告。
  - 投稿は outbox 経由（post_mode 尊重。confirmなら確認待ち、auto/semiで送信）。
  - 通知先はTODOが紐づく room_id。room_id が無いものは manager_room_id（オーナーの入口）へ。
"""
import datetime
import json

from db.connection import get_conn, query_one
from services import outbox, settings
from services import tasks as T
from services.agent_tools import format_tools, progress_tools
from services.chatwork import mention

# job_type -> (settings時刻キー, 既定時刻, 抽出kind, エスカレ段階, 見出し)
JOBS = {
    "carryover_1000": ("carryover_check_time", "10:30", "carryover", 3, "前日未完了・期限超過の確認"),
    "closing_1800": ("closing_check_time", "18:00", "today_open", 2, "終業前の未完了確認"),
    "due_reminder": ("due_reminder_check_time", "10:30", "due_reminder", 0, "期限リマインド（期限前日・前日休業日なら当日）"),
}

# 週次の全件棚卸し（日次の絞り込み催促とは別物）。job_type -> (weekday 0=月〜4=金, 時刻キー, 既定時刻, 見出し)
WEEKLY_JOBS = {
    "weekly_report_mon": (0, "weekly_report_mon_time", "10:30", "週始めの棚卸し（月曜10:30・やり残し確認）"),
    "weekly_report_fri": (4, "weekly_report_fri_time", "18:00", "週次棚卸し（金曜18:00）"),
}


def _parse_hhmm(s, default):
    try:
        h, m = s.split(":")
        return int(h), int(m)
    except Exception:
        h, m = default.split(":")
        return int(h), int(m)


def due_jobs(now: datetime.datetime):
    """今実行すべき job_type のリスト（時刻到達済み＆本日未実行）。時刻順。"""
    if settings.get_setting("scheduled_jobs_enabled", "1") != "1":
        return []
    today = now.date().isoformat()
    out = []
    for job_type, (time_key, default, _kind, _stage, _label) in JOBS.items():
        h, m = _parse_hhmm(settings.get_setting(time_key, default), default)
        target = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if now < target:
            continue  # まだ時刻前
        # 本日未実行か（claim前の事前チェック。実際の排他は claim で）
        ran = query_one("SELECT 1 FROM scheduled_runs WHERE run_date=? AND job_type=?", (today, job_type))
        if ran:
            continue
        out.append((target, job_type))
    out.sort()  # 時刻順
    return [j for _, j in out]


def _is_company_holiday(day: str) -> bool:
    """会社の休業日（年間休暇スケジュールのオレンジ）か。判定できない時は False（＝通常運転）。

    休業日に催促・進捗確認を送らないため（オーナー指示 2026-08-22）。
    休暇表が読めない／テーブルが無い環境で定時処理ごと落とさないよう、例外は握って False。
    """
    try:
        from services import holidays
        return holidays.is_holiday(day)
    except Exception:
        return False


def _claim(job_type, today):
    """scheduled_runs に行を作れたら True（＝自分が実行担当）。二重実行防止の要。"""
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO scheduled_runs (run_date, job_type) VALUES (?, ?)",
            (today, job_type),
        )
        return cur.rowcount == 1


def _finish(job_type, today, result: dict):
    with get_conn() as conn:
        conn.execute("UPDATE scheduled_runs SET result=?, ran_at=datetime('now') "
                     "WHERE run_date=? AND job_type=?",
                     (json.dumps(result, ensure_ascii=False)[:2000], today, job_type))


def _candidates(kind, today):
    """対象TODO。本日すでにAI確認済み、または直近のAI確認より後に本日中の進捗報告が
    届いているものは除外する（催促連打防止・TASK-20260824-002）。

    実例: パールハイム101電気検診(id=24)で、松本さんが17:37に進捗報告したのに、
    同じ18:00の定時確認でその報告を無視して「進捗はいかがですか」と重ねて聞いてしまった。
    last_progress_at（進捗報告のタイムスタンプ）が本日かつ last_check_at より後なら、
    その報告自体が進捗確認済みとみなし、今回のcheck対象から外す。
    """
    res = progress_tools.tasks_needing_attention(kind=kind, limit=40)
    tasks = res.get("tasks", [])
    out = []
    for t in tasks:
        lc = t.get("last_check_at")
        if lc and str(lc)[:10] == today:
            continue  # 本日確認済みはスキップ
        lp = t.get("last_progress_at")
        if lp and str(lp)[:10] == today and (not lc or lp > lc):
            continue  # 直近の確認より後に本日中の進捗報告あり＝重ねて聞かない
        out.append(t)
    return out


# ---- 業務記録リマインド（closing_1800 に同居・Stage 16・TASK-20260827-006）----
# 「日報とみなす基準」は、業務日報（daily_report.py）が実際に本文生成へ使っている
# 「その日、本人がChatworkに投稿した発言数」をそのまま流用する（監視ルーム＋AIとの
# ダイレクトチャット。daily_report.generate() の `own` と同じ数え方）。
# 新しい「日報」の定義を作ると18:30の自動生成と数字がズレるため、二重管理にしない。


def _daily_record_reminder_enabled() -> bool:
    return settings.get_setting("daily_record_reminder_enabled", "1") == "1"


def _daily_record_min_count() -> int:
    try:
        return int(settings.get_setting("daily_record_min_count", "3"))
    except (TypeError, ValueError):
        return 3


def _send_daily_record_reminders(client, today) -> int:
    """本日の発言数が閾値未満の社員へ、業務記録の入力・確認を促す。送った人数を返す。"""
    if not _daily_record_reminder_enabled():
        return 0
    from services import daily_report as DR
    min_count = _daily_record_min_count()
    sent = 0
    for p in DR.roster():
        room_id = p.get("room_id")
        if not room_id:
            continue
        count = DR.own_message_count(today, p["account_id"])
        if count >= min_count:
            continue
        header = mention(p["account_id"], p["name"])
        body = (f"{header}\n【本日の業務記録のご確認】\n"
                f"本日のChatworkでの報告がまだ{count}件です（目安{min_count}件）。\n"
                "本日対応した業務内容を入力・報告してください。18:30に自動で業務日報を作成します。")
        dedup = f"sched:daily_record_reminder:{room_id}:{p['account_id']}:{today}"
        ob = outbox.enqueue(room_id, body, kind="progress_check",
                            reason=f"業務記録件数不足({count}/{min_count}件)",
                            to_account_ids=str(p["account_id"]), dedup_key=dedup)
        if ob:
            outbox.process_auto(client)
            sent += 1
    return sent


def _decide_prompt(job_type, label, tasks, today):
    lines = []
    for t in tasks:
        lines.append(
            f"- task_id={t['id']} 内容『{t['content']}』 担当={t['assignee'] or '?'} "
            f"依頼者={t['requester'] or '?'} 期限={t['due_date'] or '未設定'} 状態={t['status']} "
            f"確認回数={t['check_count']} エスカレ段階={t['escalation_stage']} "
            f"最終進捗回答={t.get('last_progress_reply') or 'なし'} room_id={t['room_id']}"
        )
    task_block = "\n".join(lines)
    if job_type == "due_reminder":
        principle = """- これは「期限の数日前」に送る事前リマインドであり、催促ではない。原則として対象TODOは全件 contact=true にする。
- 見送ってよいのは、直近(前日以内)に進捗確認済みで順調と分かっている等、明らかに不要な場合のみ。
- escalate は使わない（常に false）。文面は穏やかに、期限が近づいていることをやさしく伝える。"""
    elif job_type == "closing_1800":
        principle = """- 対象TODOには「期限が決まっているもの」と「期限が未設定のもの」の2種類が混在する。文面はどちらか判別して使い分けること。
- 期限が決まっているもの: 従来通り、期限・優先度・停滞・確認回数・最終進捗回答を見て、本当に必要なものだけ contact=true にする（本日期限/期限超過など状況に応じた催促）。確認回数が多く未完了が続くもの（段階3以上）は、担当者への催促ではなく依頼者/管理者への「期限超過の報告」にする（escalate=true）。
- 期限が未設定のもの: 期限の有無に関わらず毎日18時の進捗確認対象。原則 contact=true にし、催促ではなく「進捗はいかがですか」という穏やかな確認メッセージにする。見送ってよいのは、直近(前日以内)に進捗確認済みで順調と分かっている等、明らかに不要な場合のみ。期限が無いため escalate は使わない（常に false）。"""
    else:
        principle = f"""- 全部を機械的に催促しない。期限・優先度・停滞・確認回数・最終進捗回答を見て、本当に必要なものだけ contact=true。
- 同じ相手に短時間で何度も同じことを聞かない。確認回数が多く未完了が続くもの（段階3以上）は、担当者への催促ではなく依頼者/管理者への「期限超過の報告」にする（escalate=true）。
- {job_type}=carryover_1000 は「前日以前が期限のまま未完了（期限超過）」と「期限未設定かつ一度もAI確認していない（AI確認待ち）」の2種類が混在する。期限超過は催促、期限未設定・未確認は「進捗はいかがですか」という穏やかな確認にする（催促口調にしない）。"""
    return f"""あなたは不動産管理会社の社内AI社員です。今は「{label}」({job_type})の時間です。
以下の未完了TODOについて、担当者へChatworkで進捗確認/催促を送るべきか、あなたが優先度と状況で判断してください。

# 判断の原則
{principle}
- メッセージは簡潔・丁寧な日本語。宛名やAI接頭辞は付けない（システムが付与）。担当者名は文中で自然に触れてよい。

# 対象TODO
{task_block}

# 出力(JSON配列のみ)
[
  {{"task_id":123, "contact":true, "escalate":false, "message":"○○の進捗はいかがですか？本日期限です。", "reason":"本日期限で未着手のため"}},
  {{"task_id":124, "contact":false, "escalate":false, "message":"", "reason":"昨日確認済みで進行中のため今回は静観"}}
]
contact=false のものは message 空でよい。"""


def _format_contact_item(t, msg):
    due = t["due_date"] or "期限未設定"
    return f"■ {t['content']}\n　　期限:{due}\n　　→ {msg}"


def run_job(client, job_type, now=None):
    now = now or datetime.datetime.now()
    today = now.date().isoformat()
    _kt, _def, kind, stage, label = JOBS[job_type]
    if not _claim(job_type, today):
        return {"job": job_type, "claimed": False}  # 既に他が実行済み（二重防止）

    # 会社の休業日は催促・進捗確認を送らない（claim 済みなのでこの日はもう走らない）。
    # 休み中に期限を過ぎたTODOは、翌営業日の carryover_1000（期限超過）で拾われる。
    if _is_company_holiday(today):
        res = {"skipped": "休業日", "candidates": 0, "contacted": 0}
        _finish(job_type, today, res)
        return {"job": job_type, "claimed": True, **res}

    # 業務記録リマインド（closing_1800限定）。TODOの有無に関わらず判定するので、
    # 「対象TODOなし」の早期returnより前でやる。失敗してもTODO確認自体は止めない。
    daily_record_reminders = 0
    daily_record_error = None
    if job_type == "closing_1800":
        try:
            daily_record_reminders = _send_daily_record_reminders(client, today)
        except Exception as e:
            daily_record_error = f"{type(e).__name__}: {e}"

    tasks = _candidates(kind, today)
    if not tasks:
        result = {"candidates": 0, "contacted": 0}
        if job_type == "closing_1800":
            result["daily_record_reminders"] = daily_record_reminders
            if daily_record_error:
                result["daily_record_error"] = daily_record_error
        _finish(job_type, today, result)
        return {"job": job_type, "claimed": True, **result}

    # Claude に「誰に何を送るか」を判断させる（1コール）
    from services.claude_client import ClaudeError, run_json
    try:
        decisions, _env = run_json(_decide_prompt(job_type, label, tasks, today),
                                   model=settings.get_setting("model_scheduler", "haiku"), timeout=300)
        if not isinstance(decisions, list):
            decisions = decisions.get("decisions", []) if isinstance(decisions, dict) else []
    except ClaudeError as e:
        _finish(job_type, today, {"error": str(e)})
        return {"job": job_type, "claimed": True, "error": str(e)}

    by_id = {t["id"]: t for t in tasks}
    mroom_setting = settings.get_setting("manager_room_id", "")
    # 担当者へ直接送るものは (room_id, 担当者) ごとにまとめる。エスカレーション（管理者への報告）は従来通り個別。
    groups = {}
    escalations = []
    for d in decisions:
        tid = d.get("task_id")
        t = by_id.get(tid)
        if not t or not d.get("contact"):
            continue
        room_id = t.get("room_id")
        if not room_id:
            continue
        msg = (d.get("message") or "").strip()
        if not msg:
            continue
        escalate = bool(d.get("escalate"))
        progress_tools.record_check(tid, escalation_stage=max(stage, t.get("escalation_stage") or 0))
        if escalate:
            # エスカレーション先: 管理者ルーム設定があればそこ、無ければ発生元ルーム。
            # 担当者本人がそのルームのメンバーとは限らないため宛先メンションは付けない。
            target_room = room_id
            if mroom_setting:
                try:
                    target_room = int(mroom_setting)
                except ValueError:
                    target_room = room_id
            escalations.append((target_room, t, msg, d))
        else:
            # 同一担当者は account_id の有無に関わらず氏名でまとめる（一部のTODOだけ
            # assignee_account_id が未解決でも、別グループ・宛先メンション欠落にしない）。
            assignee_key = t.get("assignee") or "未定"
            groups.setdefault((room_id, assignee_key), []).append((t, msg))

    contacted = 0

    # 担当者ごとに1ブロック（複数案件をまとめ、冒頭に [To:] を1回だけ付与）
    for (room_id, assignee_key), items in groups.items():
        t0 = items[0][0]
        # グループ内のいずれかのTODOに assignee_account_id があればそれを宛先に使う
        # （AI解析時に一部だけ未解決でも、同じ担当者ならメンション付きで1通にまとめる）。
        assignee_id = next((t.get("assignee_account_id") for t, _ in items if t.get("assignee_account_id")), None)
        assignee_name = t0.get("assignee") or "担当者"
        header = mention(assignee_id, assignee_name) if assignee_id else f"{assignee_name} さん"
        lines = [header, "", f"【{label}】ご確認をお願いします（{len(items)}件）"]
        for t, msg in items:
            lines.append("")
            lines.append(_format_contact_item(t, msg))
        body = "\n".join(lines)
        kind_tag = "overdue" if job_type == "carryover_1000" else "progress_check"
        dedup = f"sched:{job_type}:{room_id}:{assignee_key}:{today}"
        ob = outbox.enqueue(room_id, body, kind=kind_tag,
                            reason=f"{label}（{len(items)}件まとめ）",
                            related_task_id=t0["id"], to_account_ids=str(assignee_id or ""),
                            dedup_key=dedup)
        if ob:
            outbox.process_auto(client)
        contacted += len(items)

    # エスカレーション（管理者/依頼者への報告）は従来通り1件ずつ
    for target_room, t, msg, d in escalations:
        tid = t["id"]
        dedup = f"sched:{job_type}:{tid}:{today}"
        ob = outbox.enqueue(target_room, msg, kind="overdue",
                            reason=f"{label}: {d.get('reason','')}",
                            related_task_id=tid, to_account_ids=str(t.get("assignee_account_id") or ""),
                            dedup_key=dedup)
        if ob:
            outbox.process_auto(client)
        contacted += 1

    result = {"candidates": len(tasks), "contacted": contacted}
    if job_type == "closing_1800":
        result["daily_record_reminders"] = daily_record_reminders
        if daily_record_error:
            result["daily_record_error"] = daily_record_error
    _finish(job_type, today, result)
    return {"job": job_type, "claimed": True, **result}


def _weekly_report_due(now, job_type):
    """週次棚卸しの実行タイミングか（該当曜日・時刻到達・本日未実行）。"""
    if settings.get_setting("scheduled_jobs_enabled", "1") != "1":
        return False
    weekday, time_key, default, _label = WEEKLY_JOBS[job_type]
    if now.weekday() != weekday:
        return False
    h, m = _parse_hhmm(settings.get_setting(time_key, default), default)
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < target:
        return False
    today = now.date().isoformat()
    return not query_one("SELECT 1 FROM scheduled_runs WHERE run_date=? AND job_type=?", (today, job_type))


def _format_weekly_body(label, room_tasks):
    """担当者ごとにまとめ、期限が近いものが先に来るよう並べて読みやすく整形する。"""
    title = f"📋 {label}\n未完了TODO {len(room_tasks)}件（期限が決まっているものも含め全件）"
    return format_tools.format_grouped_task_list(room_tasks, title=title)


def run_weekly_report(client, job_type, now=None):
    """週次の全件棚卸し。progress_tools の絞り込みを通さず、未完了TODOを全件そのまま報告する。"""
    now = now or datetime.datetime.now()
    today = now.date().isoformat()
    _weekday, _time_key, _default, label = WEEKLY_JOBS[job_type]
    if not _claim(job_type, today):
        return {"job": job_type, "claimed": False}

    # 休業日は棚卸しも送らない（日次の定時確認と同じ扱い）。
    if _is_company_holiday(today):
        res = {"skipped": "休業日", "tasks": 0, "rooms": 0}
        _finish(job_type, today, res)
        return {"job": job_type, "claimed": True, **res}

    all_tasks = T.open_tasks_all()
    if not all_tasks:
        _finish(job_type, today, {"tasks": 0, "rooms": 0})
        return {"job": job_type, "claimed": True, "tasks": 0, "rooms": 0}

    fallback_room = settings.get_setting("manager_room_id", "")
    by_room = {}
    for t in all_tasks:
        room_id = t["room_id"] or fallback_room
        if not room_id:
            continue  # 通知先が無い（room_idも管理者報告先も未設定）
        by_room.setdefault(room_id, []).append(t)

    sent = 0
    for room_id, room_tasks in by_room.items():
        body = _format_weekly_body(label, room_tasks)
        dedup = f"weekly:{job_type}:{room_id}:{today}"
        ob = outbox.enqueue(room_id, body, kind="report", reason=label, dedup_key=dedup)
        if ob:
            sent += 1
    if sent:
        outbox.process_auto(client)

    result = {"tasks": len(all_tasks), "rooms": len(by_room)}
    _finish(job_type, today, result)
    return {"job": job_type, "claimed": True, **result}


def _knowledge_refresh_due(now):
    """日次ナレッジ増分リフレッシュ（1日1回）。scheduled_runsで冪等。"""
    if settings.get_setting("knowledge_refresh_enabled", "1") != "1":
        return False
    h, m = _parse_hhmm(settings.get_setting("knowledge_refresh_time", "07:00"), "07:00")
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    if now < target:
        return False
    today = now.date().isoformat()
    return not query_one("SELECT 1 FROM scheduled_runs WHERE run_date=? AND job_type='knowledge_refresh'",
                         (today,))


def run_knowledge_refresh(now=None):
    now = now or datetime.datetime.now()
    today = now.date().isoformat()
    if not _claim("knowledge_refresh", today):
        return {"job": "knowledge_refresh", "claimed": False}
    from services import config, knowledge
    src = config.get("knowledge_source_dir")
    if not src:
        _finish("knowledge_refresh", today, {"skipped": "no source dir"})
        return {"job": "knowledge_refresh", "claimed": True, "skipped": "no source"}
    try:
        res = knowledge.ingest_folder(src, incremental=True)
        summary = {k: res.get(k) for k in ("ingested", "unchanged", "skipped", "failed", "pruned")}
    except OSError as e:
        # launchd常時起動はTCCでCloudStorageを読めない場合あり（/bin/bashにFDA付与で解消）
        summary = {"error": f"フォルダ読取不可(FDA権限?): {e}"}
    except Exception as e:
        summary = {"error": f"{type(e).__name__}: {e}"}
    _finish("knowledge_refresh", today, summary)
    return {"job": "knowledge_refresh", "claimed": True, **summary}


def tick(client, now=None):
    """worker ループから毎サイクル呼ぶ。到達済み・未実行の定時ジョブを実行する。"""
    now = now or datetime.datetime.now()
    ran = []
    for job_type in due_jobs(now):
        try:
            ran.append(run_job(client, job_type, now=now))
        except Exception as e:
            ran.append({"job": job_type, "error": f"{type(e).__name__}: {e}"})
    # 週次の全件棚卸し（金曜18:00・月曜10:00。該当曜日だけ）
    for job_type in WEEKLY_JOBS:
        try:
            if _weekly_report_due(now, job_type):
                ran.append(run_weekly_report(client, job_type, now=now))
        except Exception as e:
            ran.append({"job": job_type, "error": f"{type(e).__name__}: {e}"})
    # 日次ナレッジ増分リフレッシュ
    try:
        if _knowledge_refresh_due(now):
            ran.append(run_knowledge_refresh(now=now))
    except Exception as e:
        ran.append({"job": "knowledge_refresh", "error": f"{type(e).__name__}: {e}"})
    # 業務日報（18:30・作成→Dropboxへ保管→Chatworkへアップ）
    try:
        if _daily_report_due(now):
            ran.append(run_daily_report(client, now=now))
    except Exception as e:
        ran.append({"job": DAILY_REPORT_JOB, "error": f"{type(e).__name__}: {e}"})
    # 業務月報（LINEの材料受付セッションが放置されていないかの毎サイクル確認。TASK-20260826-002）
    try:
        ran += run_monthly_report_line_check(client, now=now)
    except Exception as e:
        ran.append({"job": "monthly_report_line", "error": f"{type(e).__name__}: {e}"})
    return ran


# ---- 業務日報の自動作成・保管・アップ（Stage 10・2026-08-21 オーナー指示）----
# 毎日 18:30 に当日分をまとめて作り、Dropbox の共有フォルダへ保管し、Chatwork へアップする。
#
# ★ここは post_mode を見ない。**オーナーが「18時30分に自動的に行って」と明示指示**したため
#   （2026-08-21）。止めたいときは設定 daily_report_upload を 0 にする。
#
# ★launchd から動かすときの注意（メインPC）:
#   常時起動プロセスは CloudStorage（Dropbox）を読み書きできない。**/bin/bash に
#   フルディスクアクセス**を与えること（shorui-cabinet で同じ対処を実施済み）。
#   保管に失敗しても Chatwork へのアップは続行し、失敗した事実を管理者ルームへ知らせる。

DAILY_REPORT_JOB = "daily_report"


def _daily_report_due(now):
    if settings.get_setting("daily_report_enabled", "1") != "1":
        return False
    h, m = _parse_hhmm(settings.get_setting("daily_report_time", "18:30"), "18:30")
    if now < now.replace(hour=h, minute=m, second=0, microsecond=0):
        return False
    today = now.date().isoformat()
    return not query_one(
        "SELECT 1 FROM scheduled_runs WHERE run_date=? AND job_type=?",
        (today, DAILY_REPORT_JOB))


def _daily_report_people():
    """対象者。設定が空なら監視ルームのメンバー全員（AIを除く）。"""
    from services import daily_report as DR
    names = [n.strip() for n in
             (settings.get_setting("daily_report_people", "") or "").split(",") if n.strip()]
    roster = {p["name"]: p for p in DR.roster()}
    if names:
        return [roster[n] for n in names if n in roster]
    return list(roster.values())


def _daily_report_room_id():
    rid = settings.get_setting("daily_report_room_id", "") or \
        settings.get_setting("manager_room_id", "")
    if rid:
        return int(rid)
    row = query_one("SELECT room_id FROM rooms WHERE monitored=1 AND type='group' "
                    "ORDER BY room_id LIMIT 1")
    return row["room_id"] if row else None


def run_daily_report(client, now=None):
    """当日分の日報を作り、Dropboxへ保管し、Chatworkへアップする。"""
    import os
    from services import daily_report as DR
    from services import daily_report_export as EX

    from services import holidays

    now = now or datetime.datetime.now()
    today = now.date().isoformat()
    if not _claim(DAILY_REPORT_JOB, today):
        return {"job": DAILY_REPORT_JOB, "claimed": False}

    # 会社の休業日（年間休暇スケジュールのオレンジ）は日報を作らない。
    # claim 済みなので、この日はもう走らない（夕方じゅう再試行しない）。
    if holidays.is_holiday(today):
        res = {"date": today, "skipped": "休業日"}
        _finish(DAILY_REPORT_JOB, today, res)
        return {"job": DAILY_REPORT_JOB, "claimed": True, **res}

    result = {"date": today, "people": [], "errors": [], "saved": [],
              "uploaded": None, "mailed": None}

    # 1) 直前までの会話を取り込む（18:30 までの発言を漏らさない）
    try:
        DR.sync_from_chatwork()
    except Exception as e:
        result["errors"].append(f"sync: {type(e).__name__}: {e}")

    # 2) 1人ずつ作る（1人が失敗しても他は作る）
    people = _daily_report_people()
    rows = []
    for p in people:
        try:
            DR.generate(today, p["name"], account_id=p["account_id"],
                        generated_by="scheduled")
            result["people"].append(p["name"])
        except Exception as e:
            result["errors"].append(f"{p['name']}: {type(e).__name__}: {e}")
    order = {p["name"]: i for i, p in enumerate(people)}
    rows = sorted([r for r in DR.list_for_date(today) if r["person"] in order],
                  key=lambda r: order[r["person"]])
    if not rows:
        _finish(DAILY_REPORT_JOB, today, result)
        return {"job": DAILY_REPORT_JOB, "claimed": True, **result}

    # 3) ファイルを作る（保管先が使えなくても、アップ用に一時ファイルは必ず作る）
    import tempfile
    # ★Excel だけ作る（オーナー指示 2026-08-21）。Word は画面から手で出せる。
    tmpdir = tempfile.mkdtemp(prefix="daily_report_")
    xlsx = os.path.join(tmpdir, f"業務日報_{today}.xlsx")
    EX.build_xlsx(today, rows, xlsx)

    # 4) Dropbox の共有フォルダへ保管
    save_dir = settings.get_setting("daily_report_save_dir", "") or ""
    if save_dir:
        try:
            os.makedirs(save_dir, exist_ok=True)
            dst = os.path.join(save_dir, os.path.basename(xlsx))
            with open(xlsx, "rb") as f, open(dst, "wb") as g:
                g.write(f.read())
            result["saved"].append(dst)
        except OSError as e:
            # launchd は CloudStorage を読めない（/bin/bash にフルディスクアクセスが要る）
            result["errors"].append(f"保管失敗: {type(e).__name__}: {e}")

    # 5) Chatwork へアップ
    if settings.get_setting("daily_report_upload", "1") == "1":
        rid = _daily_report_room_id()
        if not rid:
            result["errors"].append("アップ先ルームが決まらない（daily_report_room_id 未設定）")
        else:
            wd = "月火水木金土日"[now.weekday()]
            msg = (f"{settings.get_setting('ai_prefix', '🤖AI業務マネージャー')}\n"
                   f"📝 業務日報（{now.month}月{now.day}日（{wd}）分）を作成しました。\n"
                   f"対象: {'・'.join(r['person'] for r in rows)}\n"
                   f"事実と違う点があれば直してください。")
            try:
                fid = client.post_file(rid, xlsx, message=msg)
                result["uploaded"] = {"room_id": rid, "file_id": fid}
            except Exception as e:
                result["errors"].append(f"アップ失敗: {type(e).__name__}: {e}")

    # 5-b) 社内メールへ同じExcelを添付して送る（2026-08-21 オーナー依頼）
    #      Chatworkへのアップとは独立。片方が失敗しても、もう片方は続ける。
    #      SMTP設定（secrets.toml）が無いPCでは「未設定」と記録して次へ進む。
    if settings.get_setting("daily_report_mail", "0") == "1":
        to = (settings.get_setting("daily_report_mail_to", "") or "").strip()
        if not to:
            result["errors"].append("メール送信先が未設定（daily_report_mail_to）")
        else:
            from services import mailer
            lack = mailer.missing()
            if lack:
                result["errors"].append(
                    "メール未送信: SMTPの設定が足りない（" + " / ".join(lack) + "）")
            else:
                # 件名・本文はオーナー指定の形（2026-08-21）。これ以上足さない。
                #   件名: 業務日報 2026年8月21日（金）
                #   本文: 業務日報送付 / 対象：… / 添付：<シート名>
                wd = "月火水木金土日"[now.weekday()]
                subject = f"業務日報 {now.year}年{now.month}月{now.day}日（{wd}）"
                body = ("業務日報送付\n"
                        f"対象：{'・'.join(r['person'] for r in rows)}\n"
                        f"添付：{EX.sheet_name(today)}")
                try:
                    sent = mailer.send([t.strip() for t in to.split(",") if t.strip()],
                                       subject, body, attachments=[xlsx],
                                       sender_name="AI業務マネージャー")
                    result["mailed"] = {"to": sent["to"], "attached": sent["attached"]}
                except Exception as e:
                    result["errors"].append(f"メール送信失敗: {e}")

    # 6) 失敗があれば管理者へ知らせる（黙って止まらない）
    if result["errors"]:
        try:
            from services import line_alert
            line_alert.alert(
                "📝 業務日報の自動処理で問題が出ました:\n- " + "\n- ".join(result["errors"]),
                dedup_key=f"daily_report_error:{today}")
        except Exception:
            pass

    _finish(DAILY_REPORT_JOB, today, result)
    return {"job": DAILY_REPORT_JOB, "claimed": True, **result}


# ---- 業務月報のLINEセッション放置対策（TASK-20260826-002）----
# 入力源・トリガーは「オーナーがLINEで直接送った内容」（月報開始〜月報終了）に変更した
# （line_webhook.py が受付・締めを処理する）。ここでは、締め忘れて開いたままのセッションを
# tick() のたびに確認し、一定時間（monthly_report_line_session_timeout_min・既定180分）操作が
# 無ければ自動で締め切る。締め切らないと、忘れたセッションが以降のLINE質問応答をずっと
# 材料受付として乗っ取り続けてしまう（本来のQ&Aに戻れなくなる）。
#
# ★Chatworkの資料アップロードでは今後いっさい月報を作らない（旧 run_monthly_report_check・
#   MR.pending_triggers 等は削除済み。TASK-20260826-002 オーナー指示）。


def run_monthly_report_line_check(client, now=None):
    if settings.get_setting("monthly_report_enabled", "1") != "1":
        return []
    from services import monthly_report as MR
    from services import monthly_report_line as MRL

    session = MRL.current_session()
    if not session or not MRL.is_expired(session):
        return []
    result = MR.finalize_line_session(session, client=client, generated_by="line_timeout")
    _notify_line_session_timeout(session, result)
    _alert_monthly_report_errors(result, f"line:{session['id']}")
    return [{"job": f"monthly_report_line:{session['id']}", "claimed": True, **result}]


def _notify_line_session_timeout(session, result):
    """放置後に自動で締め切ったことを、本人（LINE）へも知らせる（黙って締めない）。"""
    uid = session.get("line_user_id")
    if not uid:
        return
    if result["errors"] and "row" not in result:
        msg = ("⏰ 月報の材料受付を一定時間操作が無かったため自動的に締め切りましたが、"
               "月報を作成できませんでした:\n- " + "\n- ".join(result["errors"]))
    elif result["errors"]:
        msg = ("⏰ 月報の材料受付を一定時間操作が無かったため自動的に締め切り、"
               "月報を作成しました（一部の処理で問題がありました。管理画面をご確認ください）。")
    else:
        msg = "⏰ 月報の材料受付を一定時間操作が無かったため自動的に締め切り、月報を作成しました。"
    try:
        from services import line_client
        line_client.push(uid, msg, label="monthly_report_line_timeout")
    except Exception:
        pass


def _alert_monthly_report_errors(result, trigger_key):
    if not result["errors"]:
        return
    try:
        from services import line_alert
        line_alert.alert(
            "📝 業務月報の自動処理で問題が出ました:\n- " + "\n- ".join(result["errors"]),
            dedup_key=f"monthly_report_error:{trigger_key}")
    except Exception:
        pass
