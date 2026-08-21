"""業務日報の自動作成（Stage 10・2026-08-21）。

その日の Chatwork 会話と TODO の動きから、**社員1人ずつの業務日報**を AI が書く。

設計の要点:
  - 事実は Python が集め、文章化だけ Claude にやらせる（件数・時刻はコード側で数える）。
    → 「AIが数を間違える」余地を消し、根拠の message_id を必ず残せる。
  - その日の会話は**ルーム全体を時系列で**渡し、本人の発言に ★ を付けて示す。
    名前での本人判定はしない（「森さん(社員)」と「森様(入居者)」を取り違えるため。
    2026-08-21 の実データで実際に同居していた）。本人判定は account_id だけで行う。
  - 発言が 0 件の人は「記録なし」と明記させる。会話に無いことは書かせない。
  - Chatwork への投稿はこのモジュールでは**行わない**。積むのは outbox の pending だけ。
"""
import datetime
import json
import re

from db.connection import get_conn, query, query_one
from services import settings
from services.claude_client import run_json

# AI 自身のアカウント名（日報の対象から外す）
_AI_NAMES = ("claude",)

# --- Chatwork 記法の可読化 ---------------------------------------------------
_RE_TO = re.compile(r"\[To:(\d+)\]")
_RE_RP = re.compile(r"\[rp aid=(\d+) to=[^\]]*\]")
_RE_QTMETA = re.compile(r"\[qtmeta[^\]]*\]")
_RE_DOWNLOAD = re.compile(r"\[download:(\d+)\]")
_RE_PICON = re.compile(r"\[picon:\d+\]")
_RE_SIMPLE = re.compile(r"\[/?(?:qt|info|title|hr|code)\]")


def readable(body: str, id2name: dict) -> str:
    """Chatwork のタグを人が読める形に置き換える（宛先は名前に解決する）。"""
    s = body or ""
    s = _RE_TO.sub(lambda m: f"@{id2name.get(int(m.group(1)), m.group(1))} ", s)
    s = _RE_RP.sub(lambda m: f"↩@{id2name.get(int(m.group(1)), m.group(1))} ", s)
    s = _RE_QTMETA.sub("", s)
    s = _RE_DOWNLOAD.sub("【ファイル添付】", s)
    s = _RE_PICON.sub("", s)
    s = s.replace("[qt]", "【引用ここから】").replace("[/qt]", "【引用ここまで】")
    s = _RE_SIMPLE.sub("", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


# --- 対象者・会話の収集 -------------------------------------------------------
def id2name_map() -> dict:
    return {r["account_id"]: r["name"] for r in query("SELECT account_id, name FROM members")}


def roster(room_ids=None):
    """日報の対象になりうる人（監視ルームのメンバー。AI自身は除く）。"""
    sql = ("SELECT account_id, name, MIN(room_id) AS room_id FROM members "
           "WHERE room_id IN (SELECT room_id FROM rooms WHERE monitored=1) ")
    params = []
    if room_ids:
        sql += "AND room_id IN (%s) " % ",".join("?" * len(room_ids))
        params += list(room_ids)
    sql += "GROUP BY account_id, name ORDER BY name"
    return [dict(r) for r in query(sql, tuple(params))
            if (r["name"] or "").strip().lower() not in _AI_NAMES]


def day_bounds(date_str: str):
    d = datetime.date.fromisoformat(date_str)
    start = datetime.datetime.combine(d, datetime.time.min)
    end = start + datetime.timedelta(days=1)
    return int(start.timestamp()), int(end.timestamp())


def day_messages(date_str: str, room_ids=None):
    """対象日のメッセージを時系列で返す（監視ルームのみ）。"""
    lo, hi = day_bounds(date_str)
    sql = ("SELECT m.*, r.name AS room_name FROM messages m "
           "JOIN rooms r ON r.room_id=m.room_id "
           "WHERE m.send_time>=? AND m.send_time<? AND r.monitored=1 ")
    params = [lo, hi]
    if room_ids:
        sql += "AND m.room_id IN (%s) " % ",".join("?" * len(room_ids))
        params += list(room_ids)
    sql += "ORDER BY m.send_time, m.message_id"
    return [dict(r) for r in query(sql, tuple(params))]


def sync_from_chatwork() -> dict:
    """Chatwork の最新（各ルーム最大100件）を DB に取り込む。読むだけ・投稿はしない。

    ※ Chatwork API は過去に遡れないため、**取れるのは直近分だけ**。
      それより前の日は DB に残っている分で日報を書く。
    """
    from services.chatwork import ChatworkClient
    from services import sync
    client = ChatworkClient()
    got = 0
    for room in sync.monitored_rooms():
        try:
            got += sync.poll_room(client, room["room_id"])
        except Exception as e:  # 1ルームの失敗で止めない
            return {"new": got, "error": f"{type(e).__name__}: {e}"}
    return {"new": got, "error": None}


# --- TODO の動き ---------------------------------------------------------------
def person_tasks(date_str: str, person: str, account_id=None) -> dict:
    """その人に紐づく TODO。当日動いたもの／未完了で残っているものに分ける。"""
    cond = "(assignee_name=? OR requester=?" + (" OR assignee_account_id=?" if account_id else "") + ")"
    params = [person, person] + ([account_id] if account_id else [])
    moved = query(
        f"SELECT * FROM tasks WHERE {cond} AND date(updated_at)=? ORDER BY updated_at",
        tuple(params + [date_str]))
    open_rows = query(
        f"SELECT * FROM tasks WHERE {cond} AND status NOT IN ('完了','キャンセル') "
        "ORDER BY (due_date IS NULL), due_date LIMIT 30", tuple(params))
    return {"moved": [dict(r) for r in moved], "open": [dict(r) for r in open_rows]}


def _task_line(t: dict) -> str:
    return (f"- #{t['id']} [{t['status']}/{t['progress']}%] {t['content']}"
            f"（担当: {t['assignee_name'] or '?'} / 依頼: {t['requester'] or '?'}"
            f" / 期限: {t['due_date'] or '未確定'}）")


# --- プロンプト --------------------------------------------------------------
_PROMPT = """あなたは不動産会社「大京商事」のAI業務マネージャーです。
{date}（{wd}曜日）の Chatwork の会話と TODO の記録から、**{person} さん本人の業務日報**を書いてください。

# 絶対に守ること
- **会話・TODOに書かれていないことは書かない。** 想像で業務を作らない。
- 推測せざるを得ないことは文末に「（推測）」と付ける。
- {person} さん**本人の発言には ★ が付いています**。★の無い行は他の人の発言です。
  他人がやったことを {person} さんの実績にしない。
- 名前が似ていても別人のことがあります（社員の「森」さんと、入居者の「森様」など）。
  **本人と断定できるのは ★ が付いた発言だけ**です。
- 本人の発言が0件のときは、無理に業務を書かず「Chatwork上の記録なし」と明記し、
  他の人の発言から分かる範囲（依頼を受けた・宛先に入っていた等）だけを事実として書く。
- 数値（件数など）を自分で数えない。必要なら本文に書かず、事実の記述に留める。
- ★ は本人の発言を示す**内部の印**です。日報の文章の中に「★」や「★付き」と書かない。

# 本日の会話（{n_msgs}件・時系列）
{conversation}

# {person} さんに関係する TODO（本日動いたもの）
{tasks_moved}

# {person} さんの未完了TODO（現在）
{tasks_open}

# 出力
次のJSONだけを返してください（前後に説明文を付けない）。

{{
  "summary": "1行要約（40字以内）",
  "no_activity": true または false（本人の発言も本人に関するTODOの動きも無ければ true）,
  "body_md": "日報本文（Markdown）"
}}

body_md は次の見出しで、日本語の丁寧語（です・ます）で書いてください。
該当が無い見出しは「特になし」と書いて省略しないこと。

## 本日の対応（時系列）
- HH:MM 内容（1行1件・何を誰にしたかが分かるように）

## 対応した案件・物件
## 完了したこと
## 進行中・明日以降に持ち越すこと
## 依頼したこと・待っていること
## 気づき・注意点（AI所見）
"""


def build_prompt(date_str: str, person: str, account_id, msgs, tasks) -> str:
    id2n = id2name_map()
    lines = []
    for m in msgs:
        mark = "★" if account_id is not None and m["account_id"] == account_id else "　"
        t = datetime.datetime.fromtimestamp(m["send_time"]).strftime("%H:%M")
        text = readable(m["body"], id2n).replace("\n", "\n      ")
        lines.append(f"{mark} {t} [{m['room_name']}] {m['account_name']}: {text}")
    conversation = "\n".join(lines) if lines else "（この日の会話は記録にありません）"
    moved = "\n".join(_task_line(t) for t in tasks["moved"]) or "（本日動いたTODOはありません）"
    open_ = "\n".join(_task_line(t) for t in tasks["open"]) or "（未完了のTODOはありません）"
    wd = "月火水木金土日"[datetime.date.fromisoformat(date_str).weekday()]
    return _PROMPT.format(date=date_str, wd=wd, person=person, n_msgs=len(msgs),
                          conversation=conversation, tasks_moved=moved, tasks_open=open_)


# --- 生成・保存 ---------------------------------------------------------------
def model() -> str:
    return settings.get_setting("model_daily_report", "sonnet")


def generate(date_str: str, person: str, account_id=None, room_ids=None,
             generated_by: str = "manual") -> dict:
    """1人分の日報を作って保存し、保存した行を返す。既存があれば上書き（冪等）。"""
    msgs = day_messages(date_str, room_ids)
    own = [m for m in msgs if account_id is not None and m["account_id"] == account_id]
    tasks = person_tasks(date_str, person, account_id)
    prompt = build_prompt(date_str, person, account_id, msgs, tasks)
    parsed, env = run_json(prompt, model=model(), timeout=300)
    stats = {
        "messages_day": len(msgs),
        "messages_own": len(own),
        "tasks_moved": len(tasks["moved"]),
        "tasks_open": len(tasks["open"]),
        "tasks_done_today": len([t for t in tasks["moved"] if t["status"] == "完了"]),
    }
    body = (parsed.get("body_md") or "").strip()
    if not body:
        raise ValueError("AIが本文を返しませんでした。")
    evidence = [m["message_id"] for m in own]
    save(date_str, person, account_id, body, parsed.get("summary"), stats, evidence,
         model(), generated_by)
    _log(date_str, person, prompt, env, parsed)
    return get(date_str, person)


def save(date_str, person, account_id, body, summary, stats, evidence, model_name, generated_by):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO daily_reports (report_date, person, account_id, body, summary, stats, "
            "evidence, model, generated_by) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(report_date, person) DO UPDATE SET "
            "account_id=excluded.account_id, body=excluded.body, summary=excluded.summary, "
            "stats=excluded.stats, evidence=excluded.evidence, model=excluded.model, "
            "generated_by=excluded.generated_by, updated_at=datetime('now')",
            (date_str, person, account_id, body, summary, json.dumps(stats, ensure_ascii=False),
             json.dumps(evidence, ensure_ascii=False), model_name, generated_by))


def _log(date_str, person, prompt, env, parsed):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ai_analysis_logs (kind, model, prompt, raw_output, parsed, duration_ms) "
            "VALUES ('daily_report', ?, ?, ?, ?, ?)",
            (model(), prompt[:20000], str(env.get("result"))[:20000],
             json.dumps({"date": date_str, "person": person, **parsed}, ensure_ascii=False)[:20000],
             env.get("_elapsed_ms")))


def get(date_str: str, person: str):
    r = query_one("SELECT * FROM daily_reports WHERE report_date=? AND person=?",
                  (date_str, person))
    return dict(r) if r else None


def list_for_date(date_str: str):
    return [dict(r) for r in query(
        "SELECT * FROM daily_reports WHERE report_date=? ORDER BY person", (date_str,))]


def delete(date_str: str, person: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM daily_reports WHERE report_date=? AND person=?",
                     (date_str, person))


def to_markdown(date_str: str, rows=None) -> str:
    """1日分をまとめた Markdown（ファイル書き出し用）。"""
    rows = list_for_date(date_str) if rows is None else rows
    out = [f"# 業務日報 {date_str}", ""]
    for r in rows:
        s = json.loads(r["stats"] or "{}")
        out += [f"## {r['person']}", "",
                f"> {r['summary'] or ''}", "",
                r["body"], "",
                f"<!-- 発言{s.get('messages_own', 0)}件 / "
                f"TODO動き{s.get('tasks_moved', 0)}件 / 未完了{s.get('tasks_open', 0)}件 -->",
                "", "---", ""]
    return "\n".join(out)
