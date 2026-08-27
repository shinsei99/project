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


def day_messages(date_str: str, room_ids=None, account_id=None):
    """対象日のメッセージを時系列で返す。

    監視ルームに加え、**その社員とAIのダイレクトチャット**も読む。
    2026-08-21 以降、社員が「[To:claude] 大京西ビルの検診完了」のように AI 宛へ
    業務報告を送る運用が始まるため（グループに流さない報告を取りこぼさない）。
    ※ ただし worker が取り込むのは監視ルームだけなので、**そのダイレクトチャットも
      「ルーム設定」で監視対象にしておく**必要がある。
    """
    lo, hi = day_bounds(date_str)
    where = ["m.send_time>=?", "m.send_time<?"]
    params = [lo, hi]
    scope = ["r.monitored=1"]
    if account_id is not None:
        scope.append("(r.type='direct' AND EXISTS (SELECT 1 FROM members mb "
                     "WHERE mb.room_id=r.room_id AND mb.account_id=?))")
        params.append(account_id)
    where.append("(" + " OR ".join(scope) + ")")
    if room_ids:
        where.append("m.room_id IN (%s)" % ",".join("?" * len(room_ids)))
        params += list(room_ids)
    sql = ("SELECT m.*, r.name AS room_name FROM messages m "
           "JOIN rooms r ON r.room_id=m.room_id WHERE " + " AND ".join(where) +
           " ORDER BY m.send_time, m.message_id")
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


def own_message_count(date_str: str, account_id: int) -> int:
    """その日、本人が実際に投稿した発言数（監視ルーム＋AIとのダイレクトチャット）。

    日報本文の生成では使わず件数だけ知りたい場面（18:00の業務記録リマインド・
    Stage 16）向けの薄いラッパー。generate() 内の `own` と同じ数え方に揃える。
    """
    msgs = day_messages(date_str, account_id=account_id)
    return len([m for m in msgs if m["account_id"] == account_id])


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
- ★ は本人の発言を示す**内部の印**です。日報の文章の中に「★」や「★付き」と書かない。

# AI宛の報告も、本人がやった業務として必ず反映する
会話には、社員が AI（claude / AI業務マネージャー）宛に送った**業務報告**が混ざります。
例:「[To:claude] 大京西ビルの検診完了」「クロードさん 〇〇の鍵を返却しました」

- これは**本人が実際にやった業務の報告**です。日報に必ず反映してください。
- 「AIに報告した」「claudeへ連絡した」とは**書かない**。報告された**業務の中身**を書く。
  - 例:「[To:claude] 大京西ビルの検診完了」
    → 本日の対応「大京西ビルの検診」／完了したこと「大京西ビルの検診」
- claude / AI業務マネージャー / クロード は社内の人と同じ扱いで、**名前を本文に書かない**。
- AI（claude）**自身の発言は本人の業務ではない**ので、実績にしない
  （催促・確認・回答はAIの発言。本人が返した内容だけが本人の業務）。

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

body_md は**次の3つの見出しだけ**を、この順で書いてください。見出しを増やさない。
該当が無い見出しは「特になし」と1行だけ書く。各行は「・」ではなく `- ` で始める箇条書き。

## 本日の対応
## 完了したこと
## 進行中・持ち越し

## 本日の対応 の書き方（ここが一番大事）

**「本人が実際にやった業務」だけを書く。時刻も、依頼元も書かない。**

### ① 社内の人の名前は書かない
**社内の同僚（下記）の名前は、日報の本文に一切書かない。** 依頼元としても、
連絡・確認した相手としても書かない。社内でのやり取りは省き、業務の中身だけを書く。

  社内の人: {colleagues}

- 悪い例: 「グレイスのオーナー広告料の内訳（当社1ヶ月・業者2ヶ月）を鷲見さんに確認」
- 良い例: 「グレイスのオーナー広告料の内訳（当社1ヶ月・業者2ヶ月）を確認」
- 悪い例: 「メゾンのランドリー電灯の交換を鷲見さんより依頼され対応」
- 良い例: 「メゾンのランドリー電灯（奥2本）を交換」
- 悪い例: 「西ビル3階テナントの問合せ対応を大鹿さんより依頼を受け、対応」
- 良い例: 「西ビル3階テナント（美容室・ディークルーズ井口様）の翌日夜間のビル出入りの問合せに対応」

**社外の相手の名前は必ず残す。** オーナー・入居者・テナント・業者は業務の中身そのものなので消さない。
例:「サニカと8/26（水）午前に約束」「カリルム 片岡様へ連絡」「コーポラベリエール603号室 古田様」
「ディークルーズ井口様」はすべて正しい。

### ② 時刻は書かない
やり取りの経過を時系列に並べず、**何をしたか**を1行の要点にする。

- 悪い例: 「14:34 …問合せ対応を依頼され『承知しました』と返信」
- 良い例: 「西ビル3階テナント（美容室・ディークルーズ井口様）の翌日夜間のビル出入りの問合せに対応」

### ③「完了したこと」との関係
「本日の対応」に書いたもののうち、**その日のうちに片付いたものは「完了したこと」にも書く**。
確認が取れた・連絡がついた・作業が済んだものは完了。相手待ち・見積待ち・不在で連絡がつかなかった
ものは完了ではなく「進行中・持ち越し」に書く。

### ④ そのほか
- 「承知しました」「了承した」「返信した」といった**やり取りそのものは書かない**。
- **同じ案件についての複数のやり取りは1行にまとめる**（時系列に分けて並べない）。
- **物件名・部屋番号・入居者名・業者名は必ず残す**（後から誰が読んでも分かるように）。
- 語尾は「〜を交換」「〜に対応」「〜を確認」「〜へ連絡」「〜を報告」のように簡潔に。

### ⑤ 1つの発言に複数の物件・案件が混ざっている場合は、物件・案件ごとに行を分ける
社員が1つのメッセージの中で、複数の物件・ビル・案件をまとめて報告することがあります。
その場合、**1つの箇条書き行に複数の物件名を混在させず、物件・案件ごとに別の行に分けて**書いてください。
（「本日の対応」「完了したこと」「進行中・持ち越し」のいずれも同様に分ける。）

- 元の発言:「オーナー対応　メディックス4階　間仕切補修、東ビル　2階賃料の件」
- 悪い例（1行にまとめてしまう）:
  - オーナー対応：メディックス4階　間仕切補修、東ビル2階　賃料の件
- 良い例（物件・案件ごとに分ける）:
  - オーナー対応：メディックス4階　間仕切補修
  - オーナー対応：東ビル2階　賃料の件
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
    # 社内の人＝監視ルームのメンバー。この名前は日報の本文に出させない（社外の相手だけ残す）
    colleagues = "、".join(p["name"] for p in roster() if p["name"] != person) or "（不明）"
    return _PROMPT.format(date=date_str, wd=wd, person=person, n_msgs=len(msgs),
                          conversation=conversation, tasks_moved=moved, tasks_open=open_,
                          colleagues=colleagues)


# --- 生成・保存 ---------------------------------------------------------------
def model() -> str:
    return settings.get_setting("model_daily_report", "sonnet")


def generate(date_str: str, person: str, account_id=None, room_ids=None,
             generated_by: str = "manual") -> dict:
    """1人分の日報を作って保存し、保存した行を返す。既存があれば上書き（冪等）。"""
    msgs = day_messages(date_str, room_ids, account_id=account_id)
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


# --- 検索・集計（TASK-20260825-009・業務管理DBとしての活用） ------------------
def all_persons() -> list:
    """過去に日報が存在する氏名一覧（異動・退職済みで現在の監視ルームに居ない人も含む）。"""
    return [r["person"] for r in query(
        "SELECT DISTINCT person FROM daily_reports ORDER BY person")]


def date_range() -> tuple:
    """蓄積されている日報の最古日・最新日（無ければ None, None）。"""
    r = query_one("SELECT MIN(report_date) AS lo, MAX(report_date) AS hi FROM daily_reports")
    return (r["lo"], r["hi"]) if r else (None, None)


def search(date_from: str = None, date_to: str = None, persons=None, keyword: str = None) -> list:
    """日付範囲・氏名・キーワード（本文/要約）で日報を検索する。"""
    where, params = [], []
    if date_from:
        where.append("report_date>=?")
        params.append(date_from)
    if date_to:
        where.append("report_date<=?")
        params.append(date_to)
    if persons:
        where.append("person IN (%s)" % ",".join("?" * len(persons)))
        params += list(persons)
    if keyword:
        where.append("(body LIKE ? OR summary LIKE ?)")
        params += [f"%{keyword}%", f"%{keyword}%"]
    sql = "SELECT * FROM daily_reports"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY report_date DESC, person"
    return [dict(r) for r in query(sql, tuple(params))]


def delete(date_str: str, person: str):
    with get_conn() as conn:
        conn.execute("DELETE FROM daily_reports WHERE report_date=? AND person=?",
                     (date_str, person))


def to_markdown(date_str: str, rows=None) -> str:
    """1日分をまとめた Markdown（ファイル書き出し用）。

    本文の見出しは `##` で保存されているので、氏名の下にぶら下がるよう `###` に落とす。
    """
    from services import daily_report_export as EX
    rows = list_for_date(date_str) if rows is None else rows
    out = [f"# 業務日報 {EX.date_label(date_str)}", ""]
    for r in rows:
        body = re.sub(r"^##(?=\s)", "###", r["body"] or "", flags=re.MULTILINE)
        out += [f"## {r['person']}", "",
                f"**要約:** {r['summary'] or '-'}", "",
                body, "",
                f"_{EX.stats_label(r)}_", "",
                "---", ""]
    return "\n".join(out)
