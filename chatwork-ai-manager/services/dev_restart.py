"""開発タスクの成果を、動いている常駐サービス（launchd）へ反映する係。

なぜ要るか:
  開発エージェントは「コードを直す」ところまでしかやらない（作業中に社内サービスを落とさない
  ため、稼働中サービスの停止・再起動はプロンプトで禁止してある）。しかし launchd の常駐は
  **起動時のコードをプロセスに抱えたまま**なので、直しても再起動するまで画面には出ない。
  実際に psa-collection（図鑑をモジュールとして読み込んでいる）と brain-dump（ビルド済みを
  next start で配信）で「直したのに反映されていない」が起きている。
  そこで「開発が完了した直後」に、**触ったアプリの常駐だけ**をこの係が入れ替える。

どれを再起動するか:
  1) dev_tasks.project_dir（開発エージェントが progress ツールで報告した対象フォルダ）
  2) タスク実行中に増えたコミットで変更されたトップレベルフォルダ（git diff base..HEAD）
  この2つの和集合に**属するパスを plist が指しているラベル**だけを対象にする。

意図的にやらないこと:
  - 定時ジョブ（StartCalendarInterval / StartInterval）は触らない。kickstart は
    「その場でジョブを実行する」ので、note への自動投稿などが余計に1本出てしまう。
  - ロードされていないラベルは起動しない（pokecard-dex のように「常駐させない」と
    人が決めたものを勝手に立ち上げない）。
  - dev_restart_exclude のラベルは触らない（既定は ngrok。トンネルは自作コードではないし、
    落とすと LINE の webhook URL が切れる）。

はまりどころ（CLAUDE.md より）:
  - `launchctl kickstart -k` は**ロード済みの定義で再起動するだけ**で plist を読み直さない。
    plist 自体が書き換わっていたら bootout → bootstrap でないと反映されない。
    ここでは「plist の更新時刻 > 現プロセスの起動時刻」なら入れ替えに切り替える。
  - Next.js / Vite の常駐は**ビルド済みの成果物を配信**しているので、再起動の前に
    `npm run build` を回さないとコードを直しても何も変わらない。
"""
import os
import plistlib
import re
import subprocess
import time
import urllib.error
import urllib.request

from services import settings

LAUNCH_AGENTS_DIR = os.path.expanduser("~/Library/LaunchAgents")
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 既定で触らないラベル（ngrok は自作コードではなく、落とすと LINE の webhook URL が切れる）
DEFAULT_EXCLUDE = "com.shinsei.chatwork-ai-manager-ngrok"

_PORT_PATTERNS = (
    r"--server\.port[= ](\d{2,5})",
    r"--port[= ](\d{2,5})",
    r"(?:^|\s)-p[= ](\d{2,5})",
    r"(?:^|\s)-l[= ](\d{2,5})",
)


# ---------------------------------------------------------------- 下回り
def _sh(cmd, timeout=60, cwd=None):
    """外部コマンドを実行して (rc, 出力) を返す。例外は投げない。"""
    try:
        p = subprocess.run(cmd, cwd=cwd, timeout=timeout,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, (p.stdout or b"").decode("utf-8", "replace")
    except subprocess.TimeoutExpired:
        return 124, f"タイムアウト({timeout}秒)"
    except Exception as e:  # コマンドが無い等
        return 127, f"{type(e).__name__}: {e}"


def _domain() -> str:
    return f"gui/{os.getuid()}"


def _excluded() -> set:
    raw = settings.get_setting("dev_restart_exclude", DEFAULT_EXCLUDE) or ""
    return {s.strip() for s in raw.split(",") if s.strip()}


# ---------------------------------------------------------------- launchd
def _read_plist(path: str):
    """plist を読む。**Python の XML パーサだけでは足りない**。

    実例: `com.shinsei.note-daily.plist` は先頭のXMLコメントに `--login` と書いてあり、
    XMLの規則では `--` をコメント内に置けないため plistlib（expat）は落ちる。
    launchd と plutil は読めてしまうので、こちらも plutil に読み直させる
    （ここで黙って捨てると、そのアプリだけ永久に再起動されない）。
    """
    try:
        with open(path, "rb") as f:
            return plistlib.load(f)
    except Exception:
        pass
    rc, out = _sh(["/usr/bin/plutil", "-convert", "xml1", "-o", "-", path], timeout=20)
    if rc != 0:
        return None
    try:
        return plistlib.loads(out.encode("utf-8"))
    except Exception:
        return None


def agents() -> list:
    """~/Library/LaunchAgents の plist を読んで一覧にする。"""
    out = []
    if not os.path.isdir(LAUNCH_AGENTS_DIR):
        return out
    for name in sorted(os.listdir(LAUNCH_AGENTS_DIR)):
        if not name.endswith(".plist"):
            continue
        path = os.path.join(LAUNCH_AGENTS_DIR, name)
        pl = _read_plist(path)
        if not pl:
            continue
        args = [str(a) for a in (pl.get("ProgramArguments") or [])]
        if not args and pl.get("Program"):
            args = [str(pl["Program"])]
        out.append({
            "label": str(pl.get("Label") or name[:-6]),
            "plist": path,
            "args": args,
            "wd": pl.get("WorkingDirectory"),
            "scheduled": bool(pl.get("StartCalendarInterval") or pl.get("StartInterval")),
            "resident": bool(pl.get("KeepAlive")),
            "mtime": os.path.getmtime(path),
        })
    return out


def _paths_of(agent: dict) -> list:
    """plist が指しているパスを全部拾う（`/bin/bash -lc "…/foo.sh"` の中まで）。"""
    blob = " ".join(agent["args"] + ([agent["wd"]] if agent.get("wd") else []))
    return re.findall(r"/[^\s'\";:]+", blob)


def _is_loaded(label: str) -> bool:
    rc, _ = _sh(["/bin/launchctl", "print", f"{_domain()}/{label}"], timeout=20)
    return rc == 0


def _pid_of(label: str):
    rc, out = _sh(["/bin/launchctl", "print", f"{_domain()}/{label}"], timeout=20)
    if rc != 0:
        return None
    m = re.search(r"^\s*pid\s*=\s*(\d+)", out, re.M)
    return int(m.group(1)) if m else None


def _started_at(pid: int):
    """プロセスの起動時刻(epoch秒)。ps の etime（[[dd-]hh:]mm:ss）から逆算する。"""
    rc, out = _sh(["/bin/ps", "-o", "etime=", "-p", str(pid)], timeout=20)
    if rc != 0 or not out.strip():
        return None
    txt = out.strip()
    days = 0
    if "-" in txt:
        d, txt = txt.split("-", 1)
        days = int(d)
    parts = [int(x) for x in txt.split(":")]
    while len(parts) < 3:
        parts.insert(0, 0)
    elapsed = days * 86400 + parts[0] * 3600 + parts[1] * 60 + parts[2]
    return time.time() - elapsed


def _needs_reload(agent: dict) -> bool:
    """plist 自体が書き換わっているか（kickstart では反映されないので入れ替えが要る）。"""
    pid = _pid_of(agent["label"])
    if not pid:
        return True                      # 動いていない → 読み直して立ち上げる
    started = _started_at(pid)
    if not started:
        return False
    return agent["mtime"] > started - 5   # 5秒の余裕（起動直後の取りこぼし対策）


# ---------------------------------------------------------------- ポート・ビルド
def port_of(agent: dict):
    """待ち受けポートを plist の引数から拾う。無ければ起動スクリプトの中も見る。"""
    blob = " ".join(agent["args"])
    for pat in _PORT_PATTERNS:
        m = re.search(pat, blob)
        if m:
            return int(m.group(1))
    for p in _paths_of(agent):
        if p.endswith(".sh") and os.path.isfile(p):
            try:
                with open(p, encoding="utf-8", errors="replace") as f:
                    body = f.read()
            except OSError:
                continue
            for pat in _PORT_PATTERNS + (r"PORT[= ](\d{2,5})",):
                m = re.search(pat, body)
                if m:
                    return int(m.group(1))
    return None


def build_dir_of(agent: dict):
    """`npm run build` が要る常駐なら、そのディレクトリを返す（要らなければ None）。

    Next.js（next start）と Vite（vite preview）は**ビルド済みの成果物を配信**するので、
    ソースを直して再起動しただけでは何も変わらない。
    """
    blob = " " + " ".join(agent["args"]) + " "
    is_next = bool(re.search(r"/next\s", blob)) and " start " in blob
    is_vite = bool(re.search(r"/vite\s", blob)) and " preview " in blob
    if not (is_next or is_vite):
        return None
    d = agent.get("wd")
    if not d:
        for p in _paths_of(agent):
            if "/node_modules/" in p:
                d = p.split("/node_modules/")[0]
                break
    if d and os.path.isfile(os.path.join(d, "package.json")):
        return d
    return None


# ---------------------------------------------------------------- 対象を選ぶ
def git_head(workspace: str):
    rc, out = _sh(["/usr/bin/git", "-C", workspace, "rev-parse", "HEAD"], timeout=30)
    return out.strip() if rc == 0 else None


def push_main(workspace: str) -> dict:
    """開発タスクの完了後に、溜まっているコミットを push する（2026-08-29 オーナー指示）。

    **なぜ機械が押すのか。** 従来はエージェントに「push はしない（公開は人の判断）」と
    禁じていた。その結果コミットが未pushで溜まり、**夜の自動ジョブ（zenn-daily）の push が
    巻き添えで落ちる**事故が起きた（2026-08-29）。かといってエージェント自身に
    `git push` を許すと、任意のブランチ・force push まで書けてしまう。
    そこで **エージェントには許さないまま、完了後の定型処理として main だけを押す**。

    安全のため:
      - main 以外のブランチにいるときは押さない（意図しないブランチを公開しない）
      - force は使わない。**弾かれたらそのまま報告して終わる**（rebase もしない）
      - 押すのは「すでにコミット済みのもの」だけ。ここで新たに add / commit はしない
    """
    if settings.get_setting("dev_push_enabled", "1") != "1":
        return {"skipped": "設定で無効（dev_push_enabled=0）"}
    rc, br = _sh(["/usr/bin/git", "-C", workspace, "rev-parse", "--abbrev-ref", "HEAD"], timeout=30)
    br = (br or "").strip()
    if rc != 0 or br != "main":
        return {"skipped": f"main ではないので押さない（現在: {br or '不明'}）"}
    rc, ahead = _sh(["/usr/bin/git", "-C", workspace, "rev-list", "--count", "origin/main..HEAD"],
                    timeout=30)
    n = int((ahead or "0").strip() or 0) if rc == 0 else 0
    if n == 0:
        return {"skipped": "未pushのコミットなし"}
    rc, out = _sh(["/usr/bin/git", "-C", workspace, "push", "origin", "main"], timeout=120)
    if rc == 0:
        return {"ok": True, "count": n}
    return {"ok": False, "count": n, "error": (out or "")[-200:]}


def changed_dirs(workspace: str, base_ref: str) -> list:
    """base_ref から今までのコミットで変更されたトップレベルフォルダ（絶対パス）。"""
    if not base_ref:
        return []
    rc, out = _sh(["/usr/bin/git", "-C", workspace, "diff", "--name-only",
                   f"{base_ref}..HEAD"], timeout=60)
    if rc != 0:
        return []
    dirs = []
    for line in out.splitlines():
        top = line.strip().split("/")[0]
        if not top or "/" not in line:
            continue                       # 直下のファイル（CLAUDE.md 等）は対象にしない
        d = os.path.join(workspace, top)
        if os.path.isdir(d) and d not in dirs:
            dirs.append(d)
    return dirs


def targets(project_dir=None, workspace=None, base_ref=None) -> tuple:
    """(再起動対象のagent一覧, 対象フォルダ一覧) を返す。"""
    workspace = workspace or settings.get_setting("dev_workspace", "/Users/apple")
    home = os.path.expanduser("~")
    dirs = []
    for d in ([project_dir] if project_dir else []) + changed_dirs(workspace, base_ref):
        d = os.path.abspath(d.rstrip("/")) if d else None
        # workspace そのもの（=ホーム）を対象にすると全部の常駐が引っかかるので弾く
        if not d or d in (workspace.rstrip("/"), home) or not os.path.isdir(d):
            continue
        if d not in dirs:
            dirs.append(d)
    if not dirs:
        return [], []
    hit = []
    for a in agents():
        for p in _paths_of(a):
            if any(p == d or p.startswith(d + "/") for d in dirs):
                hit.append(a)
                break
    return hit, dirs


# ---------------------------------------------------------------- 自分自身か
def self_pids() -> set:
    """自分（worker）と、その親をたどった PID の集合。

    plist の中身（run_worker.sh）とプロセスのコマンド行（`Python worker.py`）は一致しないので、
    文字列では見分けられない。**launchd が持っているジョブの pid が自分の系統にいるか**で判定する。
    """
    pids, pid = set(), os.getpid()
    for _ in range(8):
        pids.add(pid)
        rc, out = _sh(["/bin/ps", "-o", "ppid=", "-p", str(pid)], timeout=20)
        if rc != 0 or not out.strip():
            break
        pid = int(out.strip().split()[0])
        if pid <= 1:
            break
    return pids


def is_self(agent: dict, pids=None) -> bool:
    """このプロセス（worker）を動かしている常駐か。だとすれば同期的には再起動できない。"""
    pids = pids if pids is not None else self_pids()
    job_pid = _pid_of(agent["label"])
    return bool(job_pid and job_pid in pids)


# ---------------------------------------------------------------- 実行
def _probe(port: int, wait_sec: int) -> tuple:
    """再起動後、実際に応答が返るまで待つ（HTTPコードが返れば起きているとみなす）。"""
    url = f"http://127.0.0.1:{port}/"
    deadline, last = time.time() + wait_sec, ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                return True, f"{port} HTTP {r.status}"
        except urllib.error.HTTPError as e:
            return True, f"{port} HTTP {e.code}"       # 404でもプロセスは起きている
        except Exception as e:
            last = type(e).__name__
            time.sleep(2)
    return False, f"{port} 応答なし({last})"


def restart_one(agent: dict, build=True) -> dict:
    """1つの常駐を入れ替えて、起きたことまで確かめる。"""
    label = agent["label"]
    r = {"label": label, "ok": False, "how": "", "detail": "", "skipped": ""}

    if label in _excluded():
        r.update(skipped="除外設定", ok=True)
        return r
    if agent["scheduled"] and not agent["resident"]:
        # kickstart はその場でジョブを走らせてしまう（note の自動投稿などが余計に出る）
        r.update(skipped="定時ジョブのため触らない", ok=True)
        return r
    if not _is_loaded(label):
        r.update(skipped="常駐していない（未ロード）", ok=True)
        return r

    bdir = build_dir_of(agent) if build else None
    if bdir:
        rc, out = _sh(["/bin/bash", "-lc", "npm run build"], cwd=bdir,
                      timeout=settings.get_int("dev_restart_build_timeout_sec", 900))
        if rc != 0:
            # ビルドが通らないまま再起動すると「古い成果物のまま動き続ける」ので止める
            tail = "\n".join(out.strip().splitlines()[-5:])
            r.update(how="npm run build", detail=f"ビルド失敗 rc={rc}\n{tail}")
            return r
        r["how"] = "npm run build → "

    if _needs_reload(agent):
        rc1, out1 = _sh(["/bin/launchctl", "bootout", f"{_domain()}/{label}"], timeout=60)
        time.sleep(1)
        rc2, out2 = _sh(["/bin/launchctl", "bootstrap", _domain(), agent["plist"]], timeout=60)
        r["how"] += "bootout→bootstrap"
        if rc2 != 0:
            r["detail"] = f"bootstrap 失敗 rc={rc2} {out2.strip()[:200]} / bootout rc={rc1} {out1.strip()[:120]}"
            return r
    else:
        rc, out = _sh(["/bin/launchctl", "kickstart", "-k", f"{_domain()}/{label}"], timeout=60)
        r["how"] += "kickstart"
        if rc != 0:
            r["detail"] = f"kickstart 失敗 rc={rc} {out.strip()[:200]}"
            return r

    wait = settings.get_int("dev_restart_wait_sec", 60)
    port = port_of(agent)
    if port:
        ok, detail = _probe(port, wait)
        r.update(ok=ok, detail=detail)
        return r
    # ポートを持たない常駐（sync系など）は、プロセスが立っていることだけ見る
    for _ in range(max(1, wait // 3)):
        pid = _pid_of(label)
        if pid:
            r.update(ok=True, detail=f"pid {pid}")
            return r
        time.sleep(3)
    r.update(ok=True, detail="起動を確認できず（常駐でない可能性）")
    return r


def _defer_self_restart(agent: dict):
    """自分（worker）自身の再起動。完了報告を送り終えてから、切り離した子で実行する。

    このプロセスを殺す操作なので、`start_new_session=True` で launchd のプロセスグループから
    切り離しておく（そうしないと bootout の道連れで再起動コマンドごと死ぬ）。
    """
    label, dom = agent["label"], _domain()
    if _needs_reload(agent):
        cmd = (f"sleep 5; /bin/launchctl bootout {dom}/{label}; sleep 2; "
               f"/bin/launchctl bootstrap {dom} '{agent['plist']}'")
    else:
        cmd = f"sleep 5; /bin/launchctl kickstart -k {dom}/{label}"
    subprocess.Popen(["/bin/bash", "-c", cmd], start_new_session=True,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


# ---------------------------------------------------------------- 入口
def after_task(task: dict, base_ref=None) -> dict:
    """開発タスクが完了したときに呼ぶ。戻り値の text をそのまま完了報告に足す。

    返り値: {"text": 報告文, "results": [...], "deferred": [label, ...]}
    """
    if settings.get_setting("dev_restart_enabled", "1") != "1":
        return {"text": "", "results": [], "deferred": []}
    workspace = (task or {}).get("workspace") or settings.get_setting("dev_workspace",
                                                                     "/Users/apple")
    # ★先に push する（2026-08-29 オーナー指示）。
    #   コミットが未pushで溜まると、夜の自動ジョブの push が巻き添えで落ちる。
    #   常駐の再起動対象が無いタスク（文書だけ直した等）でも押したいので、ここで先に行う。
    push = push_main(workspace)

    hits, dirs = targets((task or {}).get("project_dir"), workspace, base_ref)
    if not hits:
        return {"text": _push_text(push), "results": [], "deferred": [], "dirs": dirs,
                "push": push}

    excluded = _excluded()
    hits = [a for a in hits if a["label"] not in excluded]
    pids = self_pids()
    results, deferred = [], []
    for a in hits:
        if is_self(a, pids):
            # 自分を殺すと、この完了処理ごと消える。報告を送ってから最後に回す
            deferred.append(a)
            continue
        results.append(restart_one(a))

    lines = []
    t = _push_text(push)
    if t:
        lines.append(t)
    lines.append("🔄 反映（常駐の再起動）")
    for r in results:
        if r["skipped"]:
            lines.append(f"・{r['label']}: {r['skipped']}")
        elif r["ok"]:
            lines.append(f"・{r['label']}: {r['how']} → {r['detail']}")
        else:
            lines.append(f"・{r['label']}: ⚠️ {r['how']} {r['detail']}")
    for a in deferred:
        lines.append(f"・{a['label']}: この報告のあと再起動します（自分自身のため）")
    return {"text": "\n".join(lines), "results": results,
            "deferred": [a["label"] for a in deferred], "dirs": dirs,
            "push": push, "_deferred_agents": deferred}


def _push_text(push: dict) -> str:
    """完了報告に足す1行。**押せなかったときは黙らない**（溜まると夜のジョブが落ちる）"""
    if not push or push.get("skipped"):
        return ""
    if push.get("ok"):
        return f"⬆️ GitHubへ push しました（{push['count']}件のコミット）"
    return (f"⚠️ push できませんでした（{push.get('count')}件が未pushのまま）。"
            f"放置すると夜の自動ジョブが巻き添えで落ちます: {push.get('error','')[:120]}")


def run_deferred(info: dict) -> None:
    """after_task() の結果を渡す。自分自身の再起動を、報告送信後に発火させる。"""
    for a in (info or {}).get("_deferred_agents") or []:
        _defer_self_restart(a)
