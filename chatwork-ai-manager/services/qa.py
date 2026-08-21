"""@Claude 質問応答（RAG）。

参照優先順位（§22）:
  1. 現在/過去のChatwork会話  2. 現在のTODO  3. 案件  4. 最新の会社マニュアル/社内資料  5. 一般知識
検索は「関連チャンクだけ」を claude に渡す（§44：全ファイルを毎回渡さない）。
回答には根拠（資料名/ページ/シート）を明記し、資料に無ければ「社内資料では確認できません」と述べ、
会社ルールを勝手に創作しない（§30）。
"""
import re
import unicodedata

from db.connection import get_conn, query
from services import tasks as T
from services.claude_client import run_text

TOP_K = 12
# 内容語（漢字・カタカナ・英数）の連なり。ひらがなは助詞/活用なので区切り文字扱い。
_TOKEN_RE = re.compile(r"[一-鿿゠-ヿｦ-ﾟA-Za-z0-9]{2,}")
_STOPWORDS = {"社内資料", "確認", "教示"}


def _terms(question: str):
    """質問から検索語（内容語）を抽出。ひらがなを区切りにして漢字/カタカナ/英数の塊を取る。"""
    question = unicodedata.normalize("NFKC", question)  # 索引と同じ正規化で揺れを吸収
    raw = _TOKEN_RE.findall(question)
    terms = [t for t in raw if t not in _STOPWORDS and len(t) >= 2]
    # 長い語を優先（固有名詞・複合語を先に）
    return sorted(set(terms), key=len, reverse=True)[:10]


def search(question: str, top_k: int = TOP_K):
    """関連チャンクを返す（FTS5 trigram + 本文/文書名 LIKE フォールバック、active文書のみ）。"""
    terms = _terms(question)
    results = {}   # chunk_id -> row dict

    fts_terms = [t for t in terms if len(t) >= 3]
    if fts_terms:
        match_expr = " OR ".join(f'"{t}"' for t in fts_terms)
        try:
            rows = query(
                "SELECT c.id, c.text, c.source_ref, d.title, d.category, "
                "  bm25(knowledge_fts) AS score "
                "FROM knowledge_fts "
                "JOIN knowledge_chunks c ON c.id = knowledge_fts.rowid "
                "JOIN knowledge_documents d ON d.id = c.doc_id "
                "WHERE knowledge_fts MATCH ? AND d.active=1 "
                "ORDER BY score LIMIT ?",
                (match_expr, top_k),
            )
            for r in rows:
                results[r["id"]] = dict(r)
        except Exception:
            pass  # FTS 構文エラー等は LIKE に委ねる

    # 本文 LIKE フォールバック（2文字語・trigram 未満を拾う）
    if len(results) < top_k:
        for t in terms:
            if len(results) >= top_k * 2:
                break
            for r in query(
                "SELECT c.id, c.text, c.source_ref, d.title, d.category "
                "FROM knowledge_chunks c JOIN knowledge_documents d ON d.id=c.doc_id "
                "WHERE d.active=1 AND c.text LIKE ? LIMIT ?",
                (f"%{t}%", top_k),
            ):
                results.setdefault(r["id"], dict(r))

    # 文書名/ファイル名でもヒットさせる（「○○のマニュアルどこ？」対応）
    if len(results) < top_k:
        for t in terms:
            if len(results) >= top_k * 2:
                break
            for r in query(
                "SELECT c.id, c.text, c.source_ref, d.title, d.category "
                "FROM knowledge_documents d JOIN knowledge_chunks c ON c.doc_id=d.id "
                "WHERE d.active=1 AND (d.title LIKE ? OR d.filename LIKE ?) AND c.ord=1 LIMIT 3",
                (f"%{t}%", f"%{t}%"),
            ):
                results.setdefault(r["id"], dict(r))

    return list(results.values())[:top_k]


def _open_tasks_context(room_id=None, limit=20):
    rows = T.list_tasks(room_id=room_id)
    # AI確認待ちも含める（含めないと、そのTODOへの進捗報告が来てもエージェントが
    # 対象を見つけられない。2026-08-19 TASK-20260819-002 の実害＝§analyzer.pyと同じ穴）。
    rows = [r for r in rows if r["status"] in T.OPEN_STATUSES + [T.STATUS_WAITING, T.STATUS_AI_CONFIRM]][:limit]
    if not rows:
        return "（該当なし）"
    return "\n".join(
        f"  - {t['content']} / 担当={t['assignee_name'] or '?'} / 状態={t['status']} / 期限={t['due_date'] or '未確定'}"
        for t in rows
    )


_AI_PREFIX = "🤖AI業務マネージャー"


def _clean_body(b: str) -> str:
    """Chatworkタグ [To:..] 等と AI プレフィックスを除去（文脈にプレフィックスを混ぜないため）。"""
    b = re.sub(r"\[[^\]]*\]", "", b or "")
    b = b.replace(_AI_PREFIX, "")
    return b.strip()


# 会話履歴の方針（2026-08-17 オーナー判断）:
#   「1日の中の流れが分かればよい。それより古い話は、必要になったら検索して読み解けばよい」
#   → 直近 context_hours(既定24時間) 以内を最大 context_max(既定30件) まで渡す。
#     24時間以内に何も無ければ、冷えた状態でも最低限の流れが分かるよう直近数件だけ渡す。
#   古い話は chatwork_search / kb_search で調べる（毎回の固定費にしない）。
def _context_window():
    from services.settings import get_int
    return get_int("context_hours", 24), get_int("context_max_messages", 30)


def _chat_context(room_id, limit=None):
    """Chatworkの直近の流れ。発言時刻つき（いつの話か分からないと指示語を誤解するため）。"""
    if not room_id:
        return "（ルーム指定なし）"
    hours, cap = _context_window()
    cap = limit or cap
    cutoff = int(__import__("time").time()) - hours * 3600
    rows = query(
        "SELECT account_name, body, send_time FROM messages "
        "WHERE room_id=? AND send_time>=? ORDER BY send_time DESC, message_id DESC LIMIT ?",
        (room_id, cutoff, cap),
    )
    if not rows:   # 今日はまだ動きが無いルーム → 直近数件だけ（会話の切れ目を作らない）
        rows = query(
            "SELECT account_name, body, send_time FROM messages WHERE room_id=? "
            "ORDER BY send_time DESC, message_id DESC LIMIT 6", (room_id,))
    if not rows:
        return "（なし）"
    import datetime as _dt
    out, total = [], 0
    for r in reversed(rows):
        ts = _dt.datetime.fromtimestamp(r["send_time"]).strftime("%m/%d %H:%M")
        body = _clean_body(r["body"])[:250]
        line = f"  [{ts}] {r['account_name'] or '?'}: {body}"
        total += len(line)
        if total > 5000:      # プロンプトが膨らみすぎないよう頭打ちにする
            break
        out.append(line)
    return "\n".join(out)


def _line_history(user_id, limit=8) -> str:
    """LINEの直近のやり取りを会話履歴として返す。

    LINEには room_id が無いため `_chat_context` が「（ルーム指定なし）」を返し、
    **毎回まっさらな状態で考えていた**（2026-08-17に発覚。「1」と答えても
    何への回答か分からない／「さっきの話」が通じない、という実害が出ていた）。
    やり取りは既に ai_analysis_logs(kind='line') に保存されているので、
    新しいテーブルは作らずここから組み立てる。
    """
    if not user_id:
        return "（履歴なし）"
    hours, cap = _context_window()
    rows = query(
        "SELECT prompt, raw_output, created_at FROM ai_analysis_logs "
        "WHERE kind='line' AND prompt LIKE ? AND created_at >= datetime('now', ?) "
        "ORDER BY id DESC LIMIT ?",
        (f"[{user_id}]%", f"-{hours} hours", min(cap, 15)),
    )
    if not rows:   # 今日はまだ話していない → 直近数往復だけ（唐突に忘れたように見せない）
        rows = query(
            "SELECT prompt, raw_output, created_at FROM ai_analysis_logs "
            "WHERE kind='line' AND prompt LIKE ? ORDER BY id DESC LIMIT 3",
            (f"[{user_id}]%",))
    if not rows:
        return "（これが最初のやり取りです）"
    lines, total = [], 0
    for r in reversed(rows):
        q = re.sub(r"^\[[^\]]*\]\s*", "", r["prompt"] or "").strip()
        a = (r["raw_output"] or "").strip()
        ts = (r["created_at"] or "")[5:16]
        block = ""
        if q:
            block += f"  [{ts}] オーナー: {q[:300]}\n"
        if a:
            block += f"  [{ts}] あなた(AI): {a[:300]}\n"
        total += len(block)
        if total > 5000:
            break
        lines.append(block.rstrip())
    return "\n".join(lines)


def _pending_dev_question(channel, user_id, room_id) -> str:
    """回答待ちの開発タスクがあれば、その質問を文脈として渡す。

    これが無いと、ユーザーが選択肢に「1」とだけ答えたときに何の話か分からない
    （2026-08-17に実際に発生し、オーナーの承認が弾かれた）。
    """
    try:
        from services import dev_tasks as DT
        for t in DT.list_tasks(status=DT.WAITING_USER, limit=5):
            if channel == "line" and t.get("line_user_id") and t["line_user_id"] != user_id:
                continue
            if channel == "chatwork" and room_id and t.get("room_id") != room_id:
                continue
            return (f"\n# ⚠️ 回答待ちの開発タスクがあります\n"
                    f"{t['task_id']}「{t['title']}」で、あなたが次の質問を投げて返事を待っています:\n"
                    f"{(t.get('question') or '')[:800]}\n"
                    f"ユーザーの発言がこの質問への回答（「1」「はい」「それで」等の短い返事を含む）だと"
                    f"判断できるなら、**新しい開発タスクを作らず** "
                    f"dev_task_answer {{\"task_id\":\"{t['task_id']}\",\"answer\":\"（ユーザーの回答）\"}} "
                    f"で渡して再開させること。")
    except Exception:
        pass
    return ""


def _coverage_rule() -> str:
    """全資料の索引が未完了の間は、見つからない質問に『確認中・お待ちください』と返す。"""
    from services.settings import get_setting
    if get_setting("knowledge_full_indexed", "0") == "1":
        return ("- 社内資料で確認できないことは「社内資料では確認できません」と正直に述べる"
                "（推測で会社ルールを作らない）。")
    return ("- 社内資料に該当が見つからない場合、まだ全資料を索引に取込中のため、"
            "「その件は現在確認中です。少しお待ちください（該当資料が未取込の可能性があります）」と伝える。"
            "断定的に「ありません／確認できません」とは言わない。"
            "ただし社内業務と明らかに無関係な一般質問はこの限りでない。")


def build_prompt(question, chunks, room_id=None):
    coverage_rule = _coverage_rule()
    if chunks:
        kb = "\n\n".join(
            f"【資料: {c.get('title')}（{c.get('category')}） / 出典: {c.get('source_ref')}】\n{c['text']}"
            for c in chunks
        )
    else:
        kb = "（関連する社内資料は見つかりませんでした）"
    return f"""あなたは日本の不動産会社「大京商事」の社内AIアシスタントです。社員の質問に、会社の資料と業務データに基づいて答えます。

# 参照してよい情報の優先順位
1. 直近のChatwork会話
2. 現在のTODO・案件
3. 会社の社内資料（下記。会社独自ルールは一般論より必ず優先）
4. 一般的な知識（社内資料で確認できない場合のみ、その旨を明示して補足）

# 直近のChatwork会話
{_chat_context(room_id)}

# 現在の未完了TODO
{_open_tasks_context(room_id)}

# 関連する社内資料（抜粋。ここに無い会社ルールを創作しないこと）
{kb}

# 社員からの質問
{question}

# 回答ルール
- 社内資料を使った箇所は、末尾に「根拠: <資料名> <ページ/シート>」を必ず添える。
- 事実（資料/会話で確認できたこと）と、あなたの推測を区別する。
- Chatwork に投稿する前提の、簡潔で丁寧な日本語で答える。
- **あなたはこの経路ではTODOやデータベースを書き換える手段を一切持っていません。**
  質問が進捗報告・完了報告・依頼のような「何かを実行してほしい」内容に見えても、
  「反映しました」「更新しました」「完了にしました」「登録しました」等、何かを実行済みであるかのような
  表現を絶対に使わないこと。実行できないので、その旨と「少し時間をおいて再度お知らせください」を正直に伝える。
{coverage_rule}"""


APP_DIR = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))


def _agent_prompt(question, room_id=None, asker=None, channel="chatwork", line_user_id=None):
    from services import agent_tools
    coverage = _coverage_rule()
    catalog = agent_tools.catalog()
    room_line = f"（このやり取りのroom_id={room_id}）" if room_id else ""
    asker_line = f"質問した社員: {asker}\n" if asker else ""
    if channel == "line":
        channel_note = (
            "\n# 入口: LINE（オーナーの個人用リモコン）\n"
            "これはLINE経由でオーナー本人からの直接指示です。回答はLINEに返信されます。\n"
            "- 依頼で担当者へChatwork投稿する場合、投稿先ルーム/担当のaccount_idを chatwork_search 等で特定してから chatwork_post_message する。\n"
            "- 「今日やること」「重要な未完了」等は task_search / tasks_needing_attention で調べ、優先度を判断して要点だけ簡潔に返す。\n"
            "- LINEだからと権限は強くしない（投稿は post_mode に従う）。\n"
            "- **下の「このLINEでの直近のやり取り」は同じ相手との続きの会話。「さっきの」「それ」「1」等の指示語は必ずそこを見て解釈する。**"
        )
    else:
        channel_note = ""
    channel_note += _pending_dev_question(channel, line_user_id, room_id)
    return f"""あなたは不動産管理のプロフェッショナルであり、大京商事のオーナー/スタッフを強力に支援する優秀なAIエージェント「claude」です。LINE/Chatworkで受け取る指示に対し、最適なツールや情報源を自律的に選び、正確かつ実用的に回答します。Claude Codeのように複数ツールを反復実行してよい。
{channel_note}

# あなたが使えるツール（Bashで実行。引数はJSON1個）
すべて `python3 agent_tool.py <tool> '<JSON>'` の形で呼ぶ。結果はJSONで返る。
{catalog}
さらに WebSearch / WebFetch ツールが直接使える（ポータルサイト検索・URLの読み込み・一般の調べもの）。

# あなたの能力（「機能があるか」と聞かれたら、上記に基づき正直に答える）
社内資料検索・Chatwork履歴検索・TODO操作・案件操作・Chatwork投稿・国交省の公的データ取得・**法令の現行条文の引用（e-Gov）**・**郵便番号と住所の照合（日本郵便）**・Web検索/URL解析ができる。

# 情報源の優先順位（この順で判断・使い分ける。重要）
1. 【社内資料・プライベートデータ】社内マニュアル(22本)・レントロール・管理物件台帳・Chatwork履歴・TODO・案件。
   → 社内ルールや個別の物件・顧客の情報は、必ずまず kb_search 等でプライベートに完結させる。
   - 入居者/契約者/家賃/共益費/空室/更新＝レントロール一覧(マンション/ビル/駐車場他。入居者の正典はマンション版)。
   - 物件の基本情報(所在地/構造/戸数)＝管理物件台帳。書類の保管場所＝全ファイル一覧。手順＝業務マニュアル。
   - 「○○を作りたい」等の作業系＝該当する社内ツール(社内Webアプリ)をURL付きで案内(kb_search "社内ツール ○○")。
   - kb_search が空振りでも、全ファイル一覧やフォルダ構成・過去の回答等から該当資料の**フルパス**が
     分かる場合（契約書・申込書などのスキャン画像PDF＝未OCR）は、ユーザーに「開いて確認してください」と
     案内する前に **必ず kb_read_document でその場を読み**、内容から直接回答する
     （OCR結果は索引にも自動登録されるので次回以降 kb_search でもヒットするようになる）。
2. 【不動産の公的データ】地価・不動産取引価格の相場など客観的な数値根拠 → reinfolib_transactions / reinfolib_cities(国交省)。
2-b.【法令】「法律ではどうなっているか」「○○法の第○条」「更新拒絶/原状回復/重要事項説明の要件」等、
   **法律そのものを聞かれたら記憶で答えず law_article / law_find_articles で現行条文を引く**（e-Gov・キー不要）。
   条番号が分かれば law_article、分からなければ law_find_articles でキーワードから探す。
   回答には**条文の原文と施行日**を添える。ただし条文の引用までが役目で、**個別事案の法的判断は人が行う**
   （「一般論としてはこの条文。最終判断は担当者・専門家に」と添える）。社内の運用・書式の話は 1 の kb_search。
2-c.【住所・郵便番号】住所や郵便番号の確認・宛名書き・送付書の作成では address_to_zip / zip_lookup を使う
   （日本郵便の公式データ）。社内資料の住所は人の入力なので、**公式データと食い違ったらその旨を伝える**。
3. 【Web検索】社内・公的で足りない最新の外部情報 → WebSearch/WebFetch。
   - ポータル(SUUMO/HOME'S/at home等)の最新募集状況、設備メーカー情報、行政通達、最新ニュース、一般の調べもの・雑談。
   - 不動産以外(天気/ニュース/一般ビジネス知識等)でも制限せず WebSearch で親切に答える。

# 物件ピックアップ・客付け支援
「○○周辺で家賃○万くらいの物件を探して」等 → WebSearchで主要ポータルを横断→希望条件に合う物件を基本3件厳選→各件「概要(家賃/間取り/アクセス)・おすすめ点・注意点」を整理して提示→「ネット公開情報に基づく参考値」である旨を明記。

# URLが提示されたら
そのURLを WebFetch で読み込み、社内の管理物件や顧客希望条件との適合性を判定して「買い/借り・検討余地あり・見送り推奨」等の見解をフィードバックする。

# 進め方（Claude Codeのように反復する）
1. 質問の意図を判断（社内情報／公的データ／Web／TODO操作／案件 など）。
2. 上の優先順位で最適なツールを選び実行→結果を読み→足りなければ別ツール/別検索語で最大8回まで反復（諦めない）。
3. 物件名・号室・人名の略称/表記ゆれは正式名称を推測して再検索（例「メゾン501」→"メゾンドール都島"501号室の契約者）。同じ号室番号が複数物件にあるため対象物件を正しく特定する。

# 位置・地図の質問（GIS）
「近い/遠い」「周辺」「半径」「エリア」「地図」「どこにある」といった**場所の話が出たら GIS ツールを使う**。
記憶や推測で距離や位置関係を答えない（管理物件108件の住所と座標はDBにあり、88件は座標取得済み）。
- 「○○の近くに自社物件ある？」→ gis_nearby_properties（radius_m は言われた値。指定がなければ1000）
- 「○○と△△はどれくらい離れてる？」→ gis_distance
- 「管理物件を地図にして」「都島区の物件を地図で」→ gis_create_map（作った地図の見方は open_hint をそのまま伝える）
- 「外観を見たい」「現地の様子は」「どんな建物？」→ **streetview_link**（人が開いて見るリンク＋撮影年月）。
  リンクを送る前に有無を確かめたいときは streetview_available。**SV画像をAIに読ませない・印刷しない**
  （Google Maps規約 3.2.3(c)(vii)/Geo Guidelines）。画面で見るのは可なので、リンクを渡すのが正解。
  現地の看板・テナント名をこちらで読み取る必要があるときだけ streetview_lookup（衛星写真＋vision）を使う。
- 「このエリアに何件ある？」「どこに集中してる？」→ gis_area_stats
- 物件名があいまいなときは先に gis_property_search で特定する。
- **相場と重ねる場合は既存の reinfolib_transactions で数値を取り**、必要なら gis_create_map の
  extra_points に渡す（市場データ取得をGIS側で二重に作らない）。
- 座標が無い物件を聞かれたら gis_status で状況を確認し、「台帳の住所欄が空です」等の事実を正直に伝える。
- LINEには地図の画像を送れない。**要点（件数・近い順の物件名と距離）を文章で答え**、
  地図ファイル名と管理画面の見方を添える。

# ★あなたの役割の境界（最重要）
あなたは**調べて答える担当**です。**このシステムや他のアプリのファイルを書き換えてはいけません。**
- コードの修正・機能追加・設定ファイルの変更・スクリプトの実行による書き込みを、自分でやらない。
  「気を利かせて直しておく」もしない。**必ず dev_task_create で開発エージェントに渡す。**
- 理由: 開発エージェントには安全策（Task ID・進捗記録・危険操作での確認・Gitの作法・
  Build/テスト/ブラウザ確認・再起動の承認）が付いている。あなたにはそれが無い。
  稼働中の業務システムを、検証なしに書き換えると会社の業務が止まる。
- Bash は**調べるため**（agent_tool.py の実行・ファイルの閲覧・状況確認）に使う。
  書き込み（ファイル作成/編集/削除、git commit、プロセスの起動停止）はしない。
- 「不具合がある」「ここを直して」と言われたら → 原因の見立てまでは答えてよいが、
  修正は dev_task_create に回し「TASK-… として開発エージェントが対応します」と伝える。
- **例外なし。** 1行の修正でも、緊急に見えても、自分では直さない。

# 業務タスクと開発タスクの振り分け（重要・混同しないこと）
- 【業務】人への依頼・TODO・検索・質問・案件・相場・物件探しなど → 上のツールでその場で処理する。
- 【開発】**アプリやシステムを作る/直す**依頼（例「TODO管理アプリを作って」「請求書アプリ作って」
  「さっきのアプリにログイン機能を追加して」「昨日作ったアプリのバグを直して」「この画面をもっと使いやすくして」
  「iPhoneでも使えるようにして」）→ **自分で実装しようとしない。** dev_task_create で開発タスクを登録する。
  実装・Build・テスト・ブラウザでの動作確認・修正・Gitは、裏で動く開発エージェントが行い、
  進捗と完了はこの入口に自動で通知される。登録したら「TASK-… として開発を始めます（完了したら通知します）」と伝える。
- 見分け方: 「田中さんに○○を依頼して」＝業務TODO（task_create）。「○○アプリを作って」＝開発（dev_task_create）。
- 「開発の状況は？」「さっきのアプリは？」→ dev_task_list / dev_task_status で調べて答える。
- 開発エージェントから質問（WAITING_USER）が来ている状態でユーザーが答えたら、
  dev_task_list で対象のtask_idを特定し dev_task_answer で回答を渡す（新しい開発タスクを作らない）。

# 依頼・TODO操作の指針
- 「溜まってるTODOを教えて」「未完了のTODO一覧」「今日やること」等、**複数件のTODOを一覧で答える**質問には、
  task_search（またはtasks_needing_attention）を呼び、返り値の `formatted`（担当者ごとにグループ化＋
  状態アイコン付きで整形済みの文字列）を**そのまま**回答本文として使う。自分で箇条書きに書き直したり、
  フラットな一行リストに崩したりしない（定時TODO確認と見た目を揃えるため。TASK-20260819-003）。
  該当TODOが1件だけの質問（「○○の件どうなった？」等）では無理に使わなくてよい。
- 「田中さんに○○を明日までにお願いして」等の依頼 → まず task_search で重複確認 → 無ければ task_create（依頼者=質問者, 担当者, 期限, room_id, source_message_id を保存）。必要なら chatwork_post_message で担当者へ依頼を投稿。
- 期限変更・担当変更・内容修正は task_update（新規作成しない）。完了報告は task_complete。進捗報告は task_progress_update。
- 書込み系(task_create/update/complete, chatwork_post_message)は post_mode 設定に従い自動送信/確認待ちになる。ツールの返り(sent/queued)をそのまま信じ、結果を回答に反映する。
- **「反映しました」「更新しました」「完了にしました」等と書いてよいのは、対応するTool呼び出しの結果が
  `"ok": true` で返ってきたのを実際に確認した時だけ**。Toolを呼んでいない／`"ok": false`／
  エラーが返った場合は、絶対に成功したかのように書かない。何が起きたか（例:「対象のTODOが
  見つかりませんでした」「ツール実行がタイムアウトしました」）を正直に伝え、必要なら
  `task_search` 等で自力で立て直す。反復しても解決しなければ「今回は反映できませんでした」と述べる。

# 回答ルール（トーン）
- 結論ファースト。実務でそのまま使える簡潔かつ丁寧なトーン。
- まず必要な調査/操作を実行し、根拠を確認してから答える（推測で語らない）。
- 根拠を明示して信頼性を担保する（例「社内マニュアルによると」「国交省の取引データによると」「ポータルの最新掲載によると」＋資料名/シート/URL）。
- 情報が見つからないときは「現時点で該当するデータや情報は見つかりませんでした」と正直に伝える。
- TODO作成/投稿をした場合は実際に行った操作（「登録しました」等）を回答に含める。
- 宛先（[To:...]）や『🤖AI業務マネージャー』等の見出しは付けない（本文のみ。システムが付与）。
- **回答は必ず日本語で書く。英語で書き出さない。**（相手は日本語話者の社員。英語の技術用語は必要最小限）
- **1文目から用件に入る。** 調べた経緯・自分の状況説明・独り言を前置きにしない。
  ✗ 悪い例: 「Content not indexed — the actual contract is a scanned PDF. I confirmed ...」
  ✗ 悪い例: 「Found it」「確認しました。これを踏まえて回答します。」
  ○ 良い例: 「コーポ・ラ・ベリエール801号室の契約者は森田様です。電話番号は…」
  資料が見つからない・OCR未処理といった事情は、**結論を述べた後**に日本語で補足する。
{coverage}

# コンテキスト
{asker_line}{room_line}
## {'このLINEでの直近のやり取り（同じ相手との続きの会話）' if channel == 'line' else '直近のChatwork会話'}
{_line_history(line_user_id) if channel == 'line' else _chat_context(room_id)}

## 現在の未完了TODO
{_open_tasks_context(room_id)}

# 社員からの質問・依頼
{question}"""


# 「Content not indexed — the actual contract ...」のような**英語の内部メモが冒頭に漏れる**問題への保険。
# プロンプトでも禁じているが、モデルが独り言を書き出すことが実際にあった（2026-08-17・塚本さんへの回答）。
# 誤爆を避けるため、**先頭の文が英単語3語以上で始まる場合だけ**落とす
# （「SUUMOによると」「Google Mapsで」のような日本語文は英単語1〜2語なので消えない）。
_EN_STRICT_RE = re.compile(r"^[A-Za-z][A-Za-z'’]*(?:[\s,\-—/]+[A-Za-z][A-Za-z'’]*){2,}")  # 英単語3語以上
_EN_LOOSE_RE = re.compile(r"^[A-Za-z][A-Za-z'’]*(?:[\s,\-—/]+[A-Za-z][A-Za-z'’]*){1,}")   # 英単語2語以上
_SENT_SPLIT_RE = re.compile(r"(?<=[。．\.\!\?！？])\s*|\n+")


def strip_english_preamble(text: str):
    """冒頭に紛れ込んだ英語の内部メモを落とす。戻り: (本文, 落とした行のリスト)。

    1文目は**英単語3語以上**でないと落とさない（「Google Mapsで確認したところ」等の
    正当な日本語文を消さないため）。いったん前置きと判定できたら、続く文は
    2語以上で落とす（「I confirmed 801号室の…」のような混在文が続くのが実際のパターン）。
    """
    if not text:
        return text, []
    parts = [p for p in _SENT_SPLIT_RE.split(text) if p is not None]
    dropped = []
    i = 0
    while i < len(parts):
        s = parts[i].strip()
        if not s:
            i += 1
            continue
        pattern = _EN_LOOSE_RE if dropped else _EN_STRICT_RE
        if pattern.match(s):
            dropped.append(s)
            i += 1
            continue
        break
    if not dropped:
        return text, []
    rest = "\n".join(p for p in parts[i:] if p and p.strip()).strip()
    # 全部消えてしまうなら触らない（英語で答えるのが正しい質問だった可能性）
    return (rest, dropped) if rest else (text, [])


def _workspace_snapshot():
    """QAエージェント実行中にコードが書き換えられていないか見張るための足跡。

    QAには Write/Edit ツールを渡していないが、**Bash がある以上は書けてしまう**ので、
    プロンプトの禁止は「お願い」でしかない（2026-08-17、実際にQAが本番コードを直した）。
    強制はできないので、代わりに**破られたら必ず分かる**ようにする。
    """
    import subprocess
    try:
        p = subprocess.run(
            ["git", "-C", APP_DIR, "status", "--porcelain", "--", APP_DIR],
            capture_output=True, text=True, timeout=15)
        return p.stdout if p.returncode == 0 else None
    except Exception:
        return None      # git が無い・リポジトリ外なら見張りを諦める（本処理は止めない）


def _check_workspace_untouched(before, question, room_id):
    """実行前後で差分が増えていたら記録する（QAは書かない約束のため）。"""
    if before is None:
        return
    after = _workspace_snapshot()
    if after is None or after == before:
        return
    b = set(before.splitlines())
    changed = [ln for ln in after.splitlines() if ln not in b]
    if not changed:
        return
    note = ("QAエージェントの実行中にファイルが変更されました（本来は開発エージェントの仕事）:\n"
            + "\n".join(changed[:40]))
    print(f"[qa] ⚠️ {note}", flush=True)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO ai_analysis_logs (room_id, kind, model, prompt, raw_output) "
                "VALUES (?, 'guard', 'qa', ?, ?)",
                (room_id, question[:2000], note),
            )
    except Exception:
        pass


# 「実際にDBを更新した」という主張。task_events は task_create/update_status/update_fields/
# touch_activity のすべてが必ず書き込む共通の記録先なので、「主張はあるのに1行も増えていない」
# ＝実際には何も反映されていない、という機械的な検証ができる（2026-08-19 TASK-20260819-002）。
_ACTION_CLAIM_RE = re.compile(r"(反映しました|更新しました|完了にしました|登録しました|作成しました|変更しました)")

_FALSE_CLAIM_NOTICE = (
    "確認しましたが、システムの都合で今回はTODOへの反映ができませんでした。"
    "お手数ですが少し時間をおいて再度お知らせいただくか、管理画面でご確認ください。"
)


def _task_events_count():
    from db.connection import query as _q
    row = _q("SELECT COUNT(*) AS c FROM task_events")
    return row[0]["c"] if row else 0


def _log_guard(room_id, question, text, note):
    print(f"[qa] ⚠️ {note}", flush=True)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO ai_analysis_logs (room_id, kind, model, prompt, raw_output, error) "
                "VALUES (?, 'guard', 'qa', ?, ?, ?)",
                (room_id, question[:2000], text[:2000], note),
            )
    except Exception:
        pass


def answer(question: str, room_id=None, asker=None, channel="chatwork",
           asker_account_id=None, line_user_id=None) -> dict:
    """エージェント型: claude が共通Tool層(agent_tool.py)を反復的に使って回答/操作する。

    channel: "chatwork"（既定）/ "line"。Agent本体・Tool・DBは共通（LINE専用処理を作らない）。
    asker_account_id / line_user_id: 「依頼がどこから来たか」。開発タスク(dev_task_create)が
      結果の返し先と権限判定に使う。**プロンプトには入れず環境変数で子プロセスへ渡す**（識別子を出力しない）。
    """
    from services import claude_health
    from services.claude_client import ClaudeError, ClaudeStalledError, run_agent
    from services.settings import get_setting
    prompt = _agent_prompt(question, room_id, asker=asker, channel=channel,
                           line_user_id=line_user_id)
    env_extra = {
        "CWAI_CHANNEL": channel,
        "CWAI_ROOM_ID": room_id,
        "CWAI_REQUESTER": asker,
        "CWAI_REQUESTER_ACCOUNT_ID": asker_account_id,
        "CWAI_LINE_USER_ID": line_user_id,
    }
    snapshot = _workspace_snapshot()   # 実行前の足跡（QAがコードを触っていないかの見張り）
    events_before = _task_events_count()   # 実行前のtask_events件数（書込みが本当にあったかの見張り）
    used_fallback = False
    try:
        env = run_agent(prompt, cwd=APP_DIR, timeout=600, model=get_setting("model_qa", "sonnet"),
                        env_extra=env_extra)
        text = (env.get("result") or "").strip()
    except ClaudeStalledError as e:
        # ★詰まり（認証・接続）のときは**フォールバックを打たない**。
        #   フォールバックも同じ claude を呼ぶので必ず同じ理由で失敗し、180秒を捨てるだけになる。
        #   2026-08-19の障害では、これで利用者を 600+180=780秒（13分）待たせていた。
        #   ここで諦めて呼び出し側へ投げ、呼び出し側が依頼をキューへ預ける。
        claude_health.mark_stalled(str(e))
        raise
    except ClaudeError as e:
        # 詰まり以外（モデルがエラーを返した・出力が壊れている等）は従来どおり
        # フォールバック: 一発RAG（ツールを一切持たないため、DBは絶対に書けない）
        used_fallback = True
        chunks = search(question)
        text, env = run_text(build_prompt(question, chunks, room_id=room_id), timeout=180)
    else:
        claude_health.note_success()   # 通ったので、詰まりフラグが残っていれば解除
    _check_workspace_untouched(snapshot, question, room_id)
    text, dropped = strip_english_preamble(text)
    if dropped:
        # 何を落としたかは残す（過剰に消していないか後から検証できるように）
        _log(room_id, f"[前置き除去] {question}", "落とした行: " + " / ".join(dropped), None, [])
    # ★実行結果の検証: 「反映しました/更新しました」等と言っているのに、実際は
    #   task_events が1件も増えていない＝ツール呼び出しが成功していない（または一度も呼んでいない）。
    #   これを確認せずそのままChatworkへ送ると「言っていることとDBの中身が食い違う」実害になる
    #   （2026-08-19 実例: パールハイム101の進捗報告に『反映しました』と返信したが tasks は無更新のままだった）。
    if _ACTION_CLAIM_RE.search(text) and _task_events_count() == events_before:
        note = (f"{'フォールバック(ツールなし)' if used_fallback else 'エージェント'}経路で"
                f"『反映した』という趣旨の回答を生成しましたが、task_events が実行前後で"
                f"増えておらず、実際にはDBへの書き込みが確認できませんでした。回答を差し替えます。")
        _log_guard(room_id, question, text, note)
        text = _FALSE_CLAIM_NOTICE
    _log(room_id, question, text, env, [])
    return {"answer": text, "sources": [], "chunk_count": 0}


def _log(room_id, question, answer_text, env, chunks):
    import json
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO ai_analysis_logs (room_id, kind, model, prompt, raw_output, parsed, duration_ms) "
            "VALUES (?, 'qa', 'sonnet', ?, ?, ?, ?)",
            (room_id, question, answer_text,
             json.dumps({"sources": [c.get("source_ref") for c in chunks]}, ensure_ascii=False),
             (env or {}).get("_elapsed_ms")),
        )
