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
    rows = [r for r in rows if r["status"] in T.OPEN_STATUSES + [T.STATUS_WAITING]][:limit]
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


def _chat_context(room_id, limit=12):
    if not room_id:
        return "（ルーム指定なし）"
    rows = query(
        "SELECT account_name, body FROM messages WHERE room_id=? ORDER BY send_time DESC, message_id DESC LIMIT ?",
        (room_id, limit),
    )
    rows = list(reversed(rows))
    if not rows:
        return "（なし）"
    return "\n".join(f"  {r['account_name'] or '?'}: {_clean_body(r['body'])[:200]}" for r in rows)


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
{coverage_rule}"""


APP_DIR = __import__("os").path.dirname(__import__("os").path.dirname(__import__("os").path.abspath(__file__)))


def _agent_prompt(question, room_id=None, asker=None, channel="chatwork"):
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
            "- LINEだからと権限は強くしない（投稿は post_mode に従う）。"
        )
    else:
        channel_note = ""
    return f"""あなたは不動産管理のプロフェッショナルであり、大京商事のオーナー/スタッフを強力に支援する優秀なAIエージェント「claude」です。LINE/Chatworkで受け取る指示に対し、最適なツールや情報源を自律的に選び、正確かつ実用的に回答します。Claude Codeのように複数ツールを反復実行してよい。
{channel_note}

# あなたが使えるツール（Bashで実行。引数はJSON1個）
すべて `python3 agent_tool.py <tool> '<JSON>'` の形で呼ぶ。結果はJSONで返る。
{catalog}
さらに WebSearch / WebFetch ツールが直接使える（ポータルサイト検索・URLの読み込み・一般の調べもの）。

# あなたの能力（「機能があるか」と聞かれたら、上記に基づき正直に答える）
社内資料検索・Chatwork履歴検索・TODO操作・案件操作・Chatwork投稿・国交省の公的データ取得・Web検索/URL解析ができる。

# 情報源の優先順位（この順で判断・使い分ける。重要）
1. 【社内資料・プライベートデータ】社内マニュアル(22本)・レントロール・管理物件台帳・Chatwork履歴・TODO・案件。
   → 社内ルールや個別の物件・顧客の情報は、必ずまず kb_search 等でプライベートに完結させる。
   - 入居者/契約者/家賃/共益費/空室/更新＝レントロール一覧(マンション/ビル/駐車場他。入居者の正典はマンション版)。
   - 物件の基本情報(所在地/構造/戸数)＝管理物件台帳。書類の保管場所＝全ファイル一覧。手順＝業務マニュアル。
   - 「○○を作りたい」等の作業系＝該当する社内ツール(社内Webアプリ)をURL付きで案内(kb_search "社内ツール ○○")。
2. 【不動産の公的データ】地価・不動産取引価格の相場など客観的な数値根拠 → reinfolib_transactions / reinfolib_cities(国交省)。
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
- 「田中さんに○○を明日までにお願いして」等の依頼 → まず task_search で重複確認 → 無ければ task_create（依頼者=質問者, 担当者, 期限, room_id, source_message_id を保存）。必要なら chatwork_post_message で担当者へ依頼を投稿。
- 期限変更・担当変更・内容修正は task_update（新規作成しない）。完了報告は task_complete。進捗報告は task_progress_update。
- 書込み系(task_create/update/complete, chatwork_post_message)は post_mode 設定に従い自動送信/確認待ちになる。ツールの返り(sent/queued)をそのまま信じ、結果を回答に反映する。

# 回答ルール（トーン）
- 結論ファースト。実務でそのまま使える簡潔かつ丁寧なトーン。
- まず必要な調査/操作を実行し、根拠を確認してから答える（推測で語らない）。
- 根拠を明示して信頼性を担保する（例「社内マニュアルによると」「国交省の取引データによると」「ポータルの最新掲載によると」＋資料名/シート/URL）。
- 情報が見つからないときは「現時点で該当するデータや情報は見つかりませんでした」と正直に伝える。
- TODO作成/投稿をした場合は実際に行った操作（「登録しました」等）を回答に含める。
- 宛先（[To:...]）や『🤖AI業務マネージャー』等の見出しは付けない（本文のみ。システムが付与）。
- 検索過程の実況・独り言（「Found it」等）は書かず、最終回答本文だけを出力する。
{coverage}

# コンテキスト
{asker_line}{room_line}
## 直近のChatwork会話
{_chat_context(room_id)}

## 現在の未完了TODO
{_open_tasks_context(room_id)}

# 社員からの質問・依頼
{question}"""


def answer(question: str, room_id=None, asker=None, channel="chatwork",
           asker_account_id=None, line_user_id=None) -> dict:
    """エージェント型: claude が共通Tool層(agent_tool.py)を反復的に使って回答/操作する。

    channel: "chatwork"（既定）/ "line"。Agent本体・Tool・DBは共通（LINE専用処理を作らない）。
    asker_account_id / line_user_id: 「依頼がどこから来たか」。開発タスク(dev_task_create)が
      結果の返し先と権限判定に使う。**プロンプトには入れず環境変数で子プロセスへ渡す**（識別子を出力しない）。
    """
    from services.claude_client import ClaudeError, run_agent
    from services.settings import get_setting
    prompt = _agent_prompt(question, room_id, asker=asker, channel=channel)
    env_extra = {
        "CWAI_CHANNEL": channel,
        "CWAI_ROOM_ID": room_id,
        "CWAI_REQUESTER": asker,
        "CWAI_REQUESTER_ACCOUNT_ID": asker_account_id,
        "CWAI_LINE_USER_ID": line_user_id,
    }
    try:
        env = run_agent(prompt, cwd=APP_DIR, timeout=600, model=get_setting("model_qa", "sonnet"),
                        env_extra=env_extra)
        text = (env.get("result") or "").strip()
    except ClaudeError as e:
        # フォールバック: 従来の一発RAG
        chunks = search(question)
        text, env = run_text(build_prompt(question, chunks, room_id=room_id), timeout=180)
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
