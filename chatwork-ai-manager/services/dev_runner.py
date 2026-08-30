"""DEVELOPMENT Agent の実行係（worker のループから tick() で回す）。

    LINE / Chatwork → 既存Agent(qa) → dev_task_create（受付だけ・即応答）
                                          ↓ DB(dev_tasks)
                              worker のループ → dev_runner.tick()
                                          ↓
                        claude（Claude Code本体・全ツール＋Visual Agent）
                                          ↓
                          Workspace で実装 → Build → 起動 → ブラウザ確認 → 修正 → Git
                                          ↓
                              完了報告を依頼元の入口へ通知（notify）

設計方針:
  - **新しい常駐プロセスを作らない。** 既存 worker の1ループに間借りする（scheduler と同じ流儀）。
  - 実行は1件ずつ（同じWorkspaceを2人で触らせない）。
  - 状態は全部DB。worker が落ちても再起動で復元できる（RUNNING → RECEIVED に戻して再開）。
  - claude のセッションIDを保存し、`--resume` で「同じ開発の続き」として再開する
    （INTERRUPT への回答後・再起動後とも、最初からやり直さない）。
"""
import os
import threading
import uuid

from services import dev_restart
from services import dev_tasks as DT
from services import notify, settings
from services.claude_client import ClaudeError, ClaudeSessionError, run_dev_agent

APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_DIR = os.path.join(APP_DIR, "logs", "dev")

_lock = threading.Lock()
_thread = None          # 実行中スレッド（同時に1本だけ）
_running_task_id = None

INTERRUPT_MARK = "<<INTERRUPT>>"


def is_busy() -> bool:
    return _thread is not None and _thread.is_alive()


def current_task_id():
    return _running_task_id if is_busy() else None


# ---------------------------------------------------------------- プロンプト
def _rules_block(task: dict) -> str:
    workspace = task.get("workspace") or settings.get_setting("dev_workspace", "/Users/apple")
    return f"""# あなたの役割
あなたは会社の開発エージェントです。コードを書くだけのAIではありません。
**調査 → 理解 → 設計 → 実装 → 実行 → テスト → ブラウザで見て操作 → 問題発見 → 原因調査 →
修正 → 再実行 → 再確認 → Gitに記録** までを自分で完了させます。

# Workspace（成果物の置き場所・厳守）
- Workspace は `{workspace}` です。**新規アプリは必ず `{workspace}/<フォルダ名>` に作る。**
- Desktop / Downloads / /tmp にプロジェクトを作らない（一時ファイルの置き場としてのみ /tmp を使う）。
- 既存アプリの改修は、まず `{workspace}/CLAUDE.md` のアプリ一覧表で対象フォルダを特定する。
  一覧に無ければ `ls {workspace}` と各フォルダの README.md / package.json で確認する。
- 対象を特定したら `{workspace}/<app>/TODO.md` `SESSION_LOG.md` `README.md` を読んでから着手する
  （前任の作業・既知の罠が書いてある。同じ失敗を繰り返さないため）。

# Visual Agent（ブラウザ）— Web UI を作った/変えたら必須
`mcp__playwright__*` ツールで実際のChrome（headless）を操作できます。
- browser_navigate / browser_click / browser_type / browser_fill_form / browser_snapshot /
  browser_take_screenshot / browser_console_messages / browser_network_requests / browser_resize など。
- **「Buildが通った」だけで完了にしない。** 開発サーバを起動し、実際にページを開いて
  表示・レイアウト・文字切れ・ボタン・フォーム・主要操作・エラー表示・レスポンシブを確認する。
- DOMだけで分からない見た目の崩れは **スクリーンショットを撮って自分の目で見る**。
- 問題を見つけたら「問題があります」で終わらせず、原因を調べて直し、再起動して再確認する。
  自力で解決できる限りこのループを回す。
- 起動した開発サーバは、確認が終わったら必ず停止する（ポートを占有したままにしない）。
- 既に使われているポートは避ける（`lsof -nP -iTCP:<port> -sTCP:LISTEN` で確認。
  8503〜8540 と 3001〜3004・5175 は社内アプリが使用中）。

# 進捗の記録（節目だけでよい。細かい実況は不要）
次のコマンドで状態を更新できます（`{APP_DIR}` から実行、または絶対パスで）:
  python3 {APP_DIR}/agent_tool.py dev_task_progress '{{"task_id":"{task['task_id']}","phase":"PLANNING","note":"要件整理中"}}'
phase は PLANNING / RUNNING / TESTING のいずれか。対象プロジェクトが決まったら
`"project_dir":"{workspace}/<app>"` と `"kind":"NEW_APP"` 等も一緒に渡してください。

# Git（安全ルール）
- 着手前に `git status` `git diff` `git branch` を確認する。
- **ユーザーの未コミット変更を消さない・勝手にコミットしない。** 自分が触ったファイルだけをコミットする。
  `git add -A` や `git commit -a` は使わない（他人の変更を巻き込む）。必ずパスを指定して `git add <path>`。
- **1つのファイルに自分の変更と他人の未コミット変更が混ざっている場合**（.gitignore など）は、
  `git add -p` で自分のハンクだけを載せる。分けられないならコミットせず、報告文にその旨を書く。
- `git reset --hard` / `git clean -fd` / `git push --force` は実行しない。
- **`git push` は自分で打たない。** コミットまでで止めること。
  **完了後に仕組み側（services/dev_restart.py の push_main）が main だけを push する**
  （2026-08-29 変更）。従来は push を完全に禁じていたが、コミットが未pushで溜まり、
  夜の自動ジョブ（zenn-daily）の push が巻き添えで落ちる事故が起きたため。
  あなたが打たないのは、任意のブランチや force push まで書けてしまうのを避けるため。
- 直下リポジトリの `.gitignore` は「1行目 `*` で全無視 → `!` で個別許可」方式。
  新規アプリを作ったら `!<app>/` と `!<app>/**` の許可行を足さないと git に載らない。
  秘密情報（.env / secrets.toml / 個人情報を含むデータ）は必ず除外行を書く。

# 勝手にやらないこと（必要なら INTERRUPT する）
本番DBの削除・大量データ削除・本番への危険な変更・本番デプロイ・外部公開・課金・有料契約・
DNS/ドメイン変更・App Store/Google Play 公開・GitHubへのpush・APIキーの新規発行・
不可逆操作・重大な仕様判断・既存データを壊す可能性のある操作。
**稼働中の社内サービス（launchd常駐・worker・LINE webhook・ngrok）の停止や再起動もしない。**
作業中に落とすと社内の利用者が困るため。**あなたが `launchctl` を叩く必要はない**:
完了報告を出した直後に、システムが**あなたが触ったアプリの常駐だけ**を自動で入れ替える
（`chatwork-ai-manager/services/dev_restart.py`。Next.js/Vite は `npm run build` も自動）。
対象は「進捗ツールで報告した `project_dir`」と「あなたのコミットが触ったフォルダ」なので、
**成果は必ずコミットするか `project_dir` を報告すること**（どちらも無いと反映されない）。
再起動以外に反映の手順が要る場合（データ再取込・キャッシュ削除など）は報告文に書く。

# 逆に、いちいち聞かないこと（自分で決める）
UI配置・色・余白・一般的な技術選択・ファイル名・コンポーネント構成・軽微な仕様・
lintエラー・Buildエラー・テストエラー・UI崩れ・一般的なブラウザエラー。

# 人の判断が要るときだけ、回答の最後に次の形式で書く
{INTERRUPT_MARK}
TASK_ID: {task['task_id']}
質問内容:
（何を確認したいか）
選択肢:
1. …
2. …
推奨: 1

# 秘密情報
APIキー・トークン・パスワード・秘密鍵・Cookieを、報告文やログ・コミットに出さない。
既存の秘密情報管理（.env / .streamlit/secrets.toml）の方式に従い、コードに直書きしない。

# 最終報告（この応答の本文）
LINE/Chatworkにそのまま送られます。**日本語で10行以内**にまとめてください:
  - 何を作った/直したか、置き場所（フォルダ）
  - 実際に確認したこと（Build / テスト / ブラウザで見た結果）
  - Gitコミットの有無
  - 残っている課題（あれば）
検索過程の実況や独り言は書かないこと。"""


def _build_prompt(task: dict) -> str:
    workspace = task.get("workspace") or settings.get_setting("dev_workspace", "/Users/apple")
    head = f"""# 開発タスク {task['task_id']}
依頼者: {task.get('requester') or '(不明)'} / 入口: {task.get('channel')}
依頼内容（原文）:
{task['request']}
"""
    if task.get("project_dir"):
        head += f"\n対象プロジェクト（判明済み）: {task['project_dir']}\n"
    if task.get("answer"):
        head += f"""
# 前回あなたが質問した件へのユーザーの回答
{task['answer']}
この回答を踏まえて、**中断したところから続けて**ください（最初からやり直さない）。
"""
    if task.get("attempts", 0) > 1 and not task.get("answer"):
        head += ("\n# 注意: このタスクは中断（PC/workerの再起動など）から再開されました。"
                 "すでに出来ている成果物を確認してから、続きを進めてください。\n")
    return head + "\n" + _rules_block({**task, "workspace": workspace})


# ---------------------------------------------------------------- 実行
def _finish_interrupt(task_id: str, text: str, task: dict, session_id):
    question = text[text.find(INTERRUPT_MARK):].strip()
    DT.set_status(task_id, DT.WAITING_USER, note="INTERRUPT（ユーザー回答待ち）",
                  question=question, session_id=session_id)
    DT.add_event(task_id, "interrupt", question)
    notify.notify(task, f"確認したいことがあります。\n\n{question}\n\n"
                        f"（この返信にそのまま答えてください）")


def _base_ref(task_id: str, workspace: str):
    """このタスクに着手した時点の HEAD。何を触ったかを後で git から割り出すために使う。

    再開（INTERRUPT への回答後・worker再起動後）でも**最初の値**を使う。上書きすると
    再開前に入れたコミットが差分から消え、そのアプリの常駐が再起動されずに終わる。
    """
    for ev in reversed(DT.events(task_id, limit=300)):        # 古い順に見る
        if ev.get("event_type") == "base_ref" and (ev.get("note") or "").strip():
            return ev["note"].strip()
    head = dev_restart.git_head(workspace)
    if head:
        DT.add_event(task_id, "base_ref", head)
    return head


def _reflect(task_id: str, base_ref):
    """開発の成果を、動いている常駐サービスへ反映する（launchd の再起動）。

    ここで失敗しても完了報告は必ず出す（「作ったのに何も返ってこない」を作らない）。
    """
    try:
        info = dev_restart.after_task(DT.get(task_id), base_ref=base_ref)
    except Exception as e:
        msg = f"⚠️ 反映（常駐の再起動）に失敗しました: {type(e).__name__}: {e}"
        DT.add_event(task_id, "restart", msg)
        return {"text": msg}
    if info.get("text"):
        DT.add_event(task_id, "restart", info["text"])
    return info


def _start_text(task: dict) -> str:
    """開発開始の知らせ。**なぜ始まったのか（経緯）を必ず書く。**

    ★2026-08-30 オーナー指摘: 「🔧 開発を開始しました」だけでは、
      いきなり開発が始まったように見えて何が起きたのか分からない。
      「〇〇しようとしたら××だったので直します」まで書くこと。
    """
    title = (task.get("title") or "").strip()
    req = " ".join((task.get("request") or "").split())
    lines = ["🔧 開発を始めます。"]
    if title:
        lines.append(f"\n【直すこと】{title}")
    if req:
        # ★経緯は人が読む欄。ファイル名や関数名が並ぶ技術的な文面のときは、
        #   先頭に一言そえないと「いきなり開発が始まった」ようにしか見えない。
        techy = sum(req.count(x) for x in (".py", "()", "_", "services/")) >= 3
        if techy:
            lines.append("\n【経緯】いまのやり取りの中で不具合に当たったので、"
                         "その場で直します。技術的にはこういう内容です:")
            lines.append(f"\n{req[:200]}{'…' if len(req) > 200 else ''}")
        else:
            lines.append(f"\n【経緯】{req[:220]}{'…' if len(req) > 220 else ''}")
    lines.append("\n完了したらお知らせします。作業中もこのチャットは普通に使えます。")
    return "".join(lines)


def _done_text(task: dict, text: str) -> str:
    """完了の知らせ。中身が空・作業メモだけのときは、依頼内容で補う。

    ★2026-08-30: 完了通知に「Waiting for the git lock monitor to fire before
      committing.」という作業メモがそのまま出て、何を直したのか分からなかった。
    """
    t = (text or "").strip()
    noise = (len(t) < 40 or t.lower().startswith("waiting")
             or "git lock" in t.lower())
    if not noise:
        return f"✅ 完了しました。\n\n{t}"
    head = (task.get("title") or "").strip() or "依頼された内容"
    body = f"✅ 完了しました。\n\n【直したこと】{head}"
    if t:
        body += f"\n\n（作業メモ: {t[:120]}）"
    body += "\n\n※詳しい変更点は管理画面の開発タスクか git のコミットを見てください。"
    return body


def _run(task_id: str):
    """1タスクを最後まで走らせる（別スレッド）。"""
    global _running_task_id
    task = DT.get(task_id)
    try:
        workspace = task.get("workspace") or settings.get_setting("dev_workspace", "/Users/apple")
        log_path = os.path.join(LOG_DIR, f"{task_id}.log")
        DT.set_status(task_id, DT.RUNNING, note="開発エージェント起動",
                      workspace=workspace, log_path=log_path)
        task = DT.get(task_id)
        notify.notify(task, _start_text(task),
                      dedup_key=f"dev_start:{task_id}:{task.get('attempts')}")
        base_ref = _base_ref(task_id, workspace)

        # セッションIDは**起動前に**決めてDBへ保存する。こうしておくと、実行中にworkerごと
        # 落ちても「同じセッションの続き」として再開できる（最初からやり直さない）。
        resume = bool(task.get("session_id"))
        if not resume:
            DT.set_status(task_id, DT.RUNNING, note="セッション採番",
                          session_id=str(uuid.uuid4()))
            task = DT.get(task_id)

        def _go(sid, is_resume):
            return run_dev_agent(
                _build_prompt(DT.get(task_id)),
                cwd=workspace,
                model=settings.get_setting("dev_model", "sonnet"),
                timeout=settings.get_int("dev_timeout_sec", 3600),
                mcp_config=settings.get_setting("dev_mcp_config",
                                                os.path.expanduser("~/.mcp.json")),
                session_id=sid, resume=is_resume,
                log_path=log_path,
                env_extra={"CWAI_DEV_TASK_ID": task_id},
            )

        try:
            env = _go(task.get("session_id"), resume)
        except ClaudeSessionError as e:
            # 前回セッションが作られる前に落ちた等。新しいセッションで最初からやり直す
            DT.add_event(task_id, "note", f"セッション再開に失敗→新規セッションで再実行: {e}")
            new_sid = str(uuid.uuid4())
            DT.set_status(task_id, DT.RUNNING, note="新規セッションで再実行", session_id=new_sid)
            env = _go(new_sid, False)
        text = (env.get("result") or "").strip()
        task = DT.get(task_id)   # 実行中に progress ツールで更新されている可能性がある
        session_id = env.get("session_id") or task.get("session_id")

        if DT.get(task_id)["status"] == DT.CANCELLED:
            return
        if INTERRUPT_MARK in text:
            _finish_interrupt(task_id, text, task, session_id)
            return
        DT.set_status(task_id, DT.COMPLETED, note="完了", result=text, session_id=session_id)
        # 直したコードを、動いている常駐へ入れ替える（再起動しないと画面に出ないため）
        info = _reflect(task_id, base_ref)
        body = _done_text(task, text)
        if info.get("text"):
            body += f"\n\n{info['text']}"
        notify.notify(task, body, dedup_key=f"dev_done:{task_id}")
        # 自分自身（worker）の再起動だけは、報告を送り終えてから発火させる
        dev_restart.run_deferred(info)
    except ClaudeError as e:
        _fail(task_id, task, f"{e}")
    except Exception as e:
        _fail(task_id, task, f"{type(e).__name__}: {e}")
    finally:
        with _lock:
            _running_task_id = None


def _fail(task_id, task, msg):
    DT.set_status(task_id, DT.FAILED, note="失敗", error=msg[:2000])
    DT.add_event(task_id, "failed", msg[:2000])
    notify.notify(task or DT.get(task_id),
                  f"⚠️ 開発タスクが失敗しました。\n{msg[:500]}\n"
                  f"（ログ: logs/dev/{task_id}.log）",
                  dedup_key=f"dev_fail:{task_id}:{(task or {}).get('attempts')}")


# ---------------------------------------------------------------- worker から呼ぶ
def tick() -> dict:
    """worker のループから毎周期呼ぶ。実行待ちが1件あれば起動する（同時1本）。"""
    global _thread, _running_task_id
    if settings.get_setting("dev_agent_enabled", "1") != "1":
        return {"skipped": "disabled"}
    with _lock:
        if is_busy():
            return {"busy": _running_task_id}
        nxt = DT.next_queued()
        if not nxt:
            return {}
        max_attempts = settings.get_int("dev_max_attempts", 3)
        if nxt.get("attempts", 0) >= max_attempts:
            DT.set_status(nxt["task_id"], DT.FAILED,
                          note=f"再試行上限({max_attempts}回)に達したため中止",
                          error="再試行上限")
            return {"gave_up": nxt["task_id"]}
        if not DT.claim(nxt["task_id"]):
            return {}
        _running_task_id = nxt["task_id"]
        _thread = threading.Thread(target=_run, args=(nxt["task_id"],), daemon=True)
        _thread.start()
        return {"started": nxt["task_id"]}


def recover() -> list:
    """worker 起動時に呼ぶ。中断された開発タスクを実行待ちへ戻す（再起動復元）。

    WAITING_USER はユーザーの回答待ちなので触らない（回答が来たら自動で再開する）。
    """
    restored = []
    for t in DT.list_tasks(limit=200):
        if t["status"] in (DT.RUNNING, DT.PLANNING, DT.TESTING):
            DT.set_status(t["task_id"], DT.RECEIVED,
                          note="worker再起動により中断 → 実行待ちへ復元（セッションから再開）")
            restored.append(t["task_id"])
    return restored


def status_line() -> str:
    """管理画面・ログ用の1行サマリ。"""
    act = DT.active()
    if not act:
        return "開発タスクなし"
    return " / ".join(f"{t['task_id']}:{t['status']}" for t in act)
