#!/usr/bin/env python3
"""全アプリの「いま触れる状態か」を1画面で出す。

    python3 dev-doctor.py            # 全部
    python3 dev-doctor.py 不動産      # カテゴリで絞る（不動産 / ツール / ゲーム）
    python3 dev-doctor.py baikai     # 名前の一部で絞る

    python3 dev-doctor.py --sync     # 2台の環境差・コミット漏れを検知（作業の終わりに叩く）
    python3 dev-doctor.py --sync --fetch   # remoteを取りに行ってから比較

見るのは4点:
  依存    … `.venv` / `node_modules` があるか（**gitで来ないので各PCで作る**）
  機密    … `.env` などが要るアプリか、あるか（**gitで来ない。メインPCから運ぶ**）
  待受    … `run.sh` のバインド先。ツール分類が `0.0.0.0` なら**LANに晒されている**
  起動    … 実際に待ち受けているか（launchd常駐や手動起動の確認）

`--sync` で見るのはこの4点（**2台のPCで差が出るのはここだけ**）:
  Git       … branch / HEAD / remoteとの差 / 未コミット / stash / ローカルだけのブランチ
              ＋**ignoreされていてgitに入っていないソース候補**（許可行が無いと他PCへ渡らない）
  バージョン … `.python-version` / `.nvmrc` と実際の python3 / node の照合
  機密       … `secrets-manifest.txt` の在り・不足（**値は絶対に表示しない**）
  自動起動   … launchd のロード状況・plistの残り・無効化の有無・cron・LANに出ている待受

不足の直し方は `./dev-setup.sh <アプリ名>`。詳細は SETUP.md。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent

# 分類は CLAUDE.md のアプリ一覧に合わせる（社内LAN共有の可否がここで決まる）
CATEGORIES: dict[str, list[str]] = {
    "不動産": [
        "handwriting-ocr", "quote-generator", "property-notice-generator", "maisoku-converter",
        "photo-inpainter", "restoration-calculator", "realestate-valuation", "settlement-creator",
        "legal-crosscheck", "madori-tracer", "theta-viewer", "tokuyaku-generator",
        "payment-reconciler", "image-resizer", "tsuikyaku-crm", "jyuusetsu-research",
        "baikai-generator", "ai-ticket-counter", "building-manager", "owner-payout-tracker",
        "file-finder", "realestate-calc", "gyomu-manual", "parking-map", "memorandum-generator",
        "soufu-maker", "shorui-cabinet", "shorui-mobile", "agent-platform", "chatwork-ai-manager",
        "business-plan-generator",
    ],
    "ツール": [
        "soufu-generator", "digital-shosai", "brain-dump", "scrapmemo-petapeta", "petapeta-extension",
        "swim-tracker-react", "mom-counter", "mail-merge-pro", "photo-remake", "kaitori-dm-maker",
        "psa-collection", "pasha-calo", "pokecard-dex", "flyer-creator", "ai-tools-base",
    ],
    "ゲーム": ["piyo-defense", "color-gravity", "cyborg-defense", "neko-escape", "nyanko-ice", "neon-blocks"],
}

SECRET_FILES = (".env", ".env.local", ".secret_key")

# venv を作らないアプリ（ルート CLAUDE.md の決まり。dev-setup.sh と揃える）
NO_VENV = {"chatwork-ai-manager"}

# **メインPCでのみ動かす「本体」プロセス。** 管理画面（8540）はどのPCで開いてもよい。
# worker / LINE webhook / ngrok を2台で動かすと、Chatwork・LINEへ二重返信し、
# ngrokの固定ドメインを奪い合う。→ 起動していたら警告する
def _main_pc_only_running(live: dict[int, str]) -> str:
    """本体（worker / LINE webhook / ngrok）がこのPCで動いていたら、その名前を返す。

    **`ps` の全文検索はやらない。** 検査中のコマンド行自体に
    "run_worker.sh" 等の文字列が入っていると、自分を検出してしまうため（実際に踏んだ）。
    プロセス名と待ち受けポートで判定する。
    """
    found = []
    if 8530 in live:
        found.append("LINE webhook(8530)")
    for name, pat in (("worker", "chatwork-ai-manager/worker"), ("ngrok", "^ngrok$")):
        try:
            r = subprocess.run(["pgrep", "-f", pat], capture_output=True, timeout=10)
            if r.returncode == 0 and r.stdout.strip():
                found.append(name)
        except Exception:
            pass
    return ",".join(found)


def _system_deps_ok(p: Path) -> bool:
    """システムPythonで主要な依存が入っているか（.deps か site-packages のどちらか）"""
    if (p / ".deps").exists():
        return True
    try:
        r = subprocess.run(
            ["/usr/bin/python3", "-c", "import streamlit"], capture_output=True, timeout=30
        )
        return r.returncode == 0
    except Exception:
        return False


def listening_ports() -> dict[int, str]:
    """いま待ち受けているポート → バインド先"""
    out: dict[int, str] = {}
    try:
        res = subprocess.run(
            ["lsof", "-nP", "-iTCP", "-sTCP:LISTEN"], capture_output=True, text=True, timeout=10
        )
    except Exception:
        return out
    for line in res.stdout.splitlines()[1:]:
        m = re.search(r"(\S+):(\d+)\s+\(LISTEN\)", line)
        if m:
            out[int(m.group(2))] = m.group(1)
    return out


def scan(app: str, live: dict[int, str]) -> dict:
    p = ROOT / app
    info: dict = {"app": app, "exists": p.is_dir()}
    if not p.is_dir():
        return info

    py = (p / "requirements.txt").exists()
    node = (p / "package.json").exists()
    info["kind"] = "python" if py else ("node" if node else "static")

    # 依存
    # chatwork-ai-manager は venv を使わない（venvのPythonから claude を呼ぶと SIGSEGV）。
    # システムPython＋`.deps` で動かすので、.venv が無くても正常。
    if py and app in NO_VENV:
        info["deps"] = "ok(sys)" if _system_deps_ok(p) else "要導入"
    elif py:
        info["deps"] = "ok" if (p / ".venv").exists() else "要作成"
    elif node:
        info["deps"] = "ok" if (p / "node_modules").exists() else "要作成"
    else:
        info["deps"] = "不要"

    # 機密（.env.example があるのに実体が無ければ「要」）
    has = [f for f in SECRET_FILES if (p / f).exists()]
    example = (p / ".env.example").exists() or (p / ".env.local.example").exists()
    info["secret"] = ",".join(has) if has else ("**要**" if example else "-")

    # run.sh からポートとバインド先を読む
    run = p / "run.sh"
    port, bind = None, None
    if run.exists():
        t = run.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"--server\.port[= ]+(\d+)", t) or re.search(r"(?:PORT|port)[= ](\d{4})", t)
        if m:
            port = int(m.group(1))
        m = re.search(r"--server\.address[= ]+([\d.]+)", t)
        if m:
            bind = m.group(1)
    info["port"] = port
    info["bind"] = bind
    info["live"] = live.get(port) if port else None
    return info


# ============================================================================
# 環境の同一性チェック（2台のPCで差が出る場所だけを見る）
#   ここが `--sync`。**作業の終わりに毎回これを叩く**のが今の運用の要。
#   直すのは人。ここでは勝手にcommit・pull・installはしない。
# ============================================================================

WARNINGS: list[str] = []


def _git(*args: str) -> str:
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=60)
        return r.stdout.strip()
    except Exception:
        return ""


def _looks_like_source(path: str) -> bool:
    """「本来gitに入れるべきなのに ignore されている」候補か。

    直下 `.gitignore` は 1行目から `*` で全部無視し `!` で個別に許可する方式なので、
    **新規ファイルは `git add` してもエラーを出さずに無視される**（2026-08-16に実際に踏んだ）。
    生成物・依存・データ・機密は除いて、ソースと文書だけを候補に出す。
    """
    if not path.endswith((".py", ".sh", ".ts", ".tsx", ".js", ".jsx", ".md", ".toml", ".yml", ".yaml")):
        return False
    skip = ("node_modules/", ".venv/", ".next/", "dist/", "build/", "/data/", "output/", "site/",
            "samples/", ".see/", "__pycache__", ".claude/", "next-env.d.ts", "secrets.toml",
            ".streamlit/", "chatwork-ai-manager/")   # chatwork の文書は意図的にgit外
    return not any(s in path for s in skip)


def check_git(do_fetch: bool) -> None:
    print("\n■ Git")
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    head = _git("log", "-1", "--format=%h %ad %s", "--date=short")
    print(f"  branch : {branch}")
    print(f"  HEAD   : {head}")

    if do_fetch:
        _git("fetch", "--prune")
        print("  remote : fetch した（最新と比較）")
    else:
        print("  remote : fetch していない（--fetch を付けると取りに行く）")
    counts = _git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
    if counts:
        behind, ahead = (counts.split() + ["?", "?"])[:2]
        state = "同期" if behind == "0" and ahead == "0" else f"remoteより {ahead} 進み / {behind} 遅れ"
        print(f"  差分   : {state}")
        if ahead != "0":
            WARNINGS.append(f"push していないコミットが {ahead} 件ある（`git push origin {branch}`）")
        if behind != "0":
            WARNINGS.append(f"remote に {behind} 件の未取得コミットがある（`git pull origin {branch}`）")

    porcelain = _git("status", "--porcelain")
    tracked = [l for l in porcelain.splitlines() if not l.startswith("??")]
    untracked = [l[3:] for l in porcelain.splitlines() if l.startswith("??")]
    print(f"  未コミット変更 : {len(tracked)} 件")
    print(f"  未追跡ファイル : {len(untracked)} 件")
    if tracked:
        WARNINGS.append(f"未コミット変更が {len(tracked)} 件ある（`git diff --stat` で中身を見る）")
        for l in tracked[:10]:
            print(f"    {l}")
    if untracked:
        WARNINGS.append(f"未追跡ファイルが {len(untracked)} 件ある（要るものなら add する）")

    # ★ 今回の事故の真因を検知する部分
    ignored = [l[3:] for l in _git("status", "--ignored", "--porcelain").splitlines()
               if l.startswith("!!")]
    suspects = [p for p in ignored if _looks_like_source(p)]
    print(f"  ignoreされているソース候補 : {len(suspects)} 件"
          f"{'（.gitignore に許可行 `!path` が必要かもしれない）' if suspects else ''}")
    for p in suspects[:10]:
        print(f"    {p}")
    if suspects:
        WARNINGS.append(f"gitに入っていないソース候補が {len(suspects)} 件（許可行が無いと他PCへ渡らない）")

    stash = [l for l in _git("stash", "list").splitlines() if l]
    print(f"  stash  : {len(stash)} 件")
    for l in stash:
        print(f"    {l}")
    if stash:
        WARNINGS.append(f"stash が {len(stash)} 件ある（他PCへは渡らない。中身を確認すること）")

    # remote に無いローカルブランチ＝このPCにしか無い作業
    local_only = [b.strip() for b in _git("branch", "--format=%(refname:short) %(upstream)").splitlines()
                  if b and len(b.split()) == 1 and b.split()[0] != branch]
    if local_only:
        print(f"  remoteを追跡していないローカルブランチ : {', '.join(local_only)}")
        WARNINGS.append(f"ローカルだけのブランチがある: {', '.join(local_only)}（消さずに確認）")


def check_versions() -> None:
    print("\n■ バージョン（.python-version / .nvmrc が基準）")

    def actual(cmd: list[str]) -> str:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            return re.sub(r"[^0-9.]", "", (r.stdout or r.stderr).split()[-1])
        except Exception:
            return "不明"

    for name, pin_file, cmd in (("Python", ".python-version", ["/usr/bin/python3", "-V"]),
                                ("Node", ".nvmrc", ["node", "-v"])):
        pin_path = ROOT / pin_file
        pin = pin_path.read_text().strip() if pin_path.exists() else None
        got = actual(cmd)
        if pin is None:
            print(f"  {name:7}: {got}（基準ファイル {pin_file} が無い）")
            WARNINGS.append(f"{pin_file} が無い（2台でバージョンが揃っている保証がない）")
        elif pin == got:
            print(f"  {name:7}: {got}  = 基準どおり")
        else:
            print(f"  {name:7}: {got}  ≠ 基準 {pin}")
            WARNINGS.append(f"{name} が基準({pin})と違う: {got}")
    print("  ※ pyenv / nvm は入っていないので自動切替はしない。**差を知らせるだけ**")


def check_secrets() -> None:
    """secrets-manifest.txt に載っているものが在るか。**値は絶対に表示しない。**"""
    man = ROOT / "secrets-manifest.txt"
    print("\n■ 機密（値は表示しない。在るか無いかだけ）")
    if not man.exists():
        print("  secrets-manifest.txt が無い")
        return
    paths = [l.strip() for l in man.read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    missing = [p for p in paths if not (ROOT / p).exists()]
    print(f"  一覧 {len(paths)} 件 → 設定済み {len(paths)-len(missing)} 件 / 不足 {len(missing)} 件")
    for p in missing:
        print(f"    不足: {p}")
    if missing:
        WARNINGS.append(f"機密が {len(missing)} 件不足（Dropbox の受け渡しで運ぶ。git には入れない）")


def check_autostart() -> None:
    """サブPCの原則は「常駐ゼロ」。ロード済み・plistの残り・無効化の状態を見る。"""
    print("\n■ 自動起動（このPCはサブPC＝常駐させない）")
    loaded = [l.split()[-1] for l in
              subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout.splitlines()
              if "com.shinsei" in l]
    agents = sorted(p.stem for p in (Path.home() / "Library/LaunchAgents").glob("com.shinsei.*.plist"))
    uid = subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()
    dis = subprocess.run(["launchctl", "print-disabled", f"gui/{uid}"],
                         capture_output=True, text=True).stdout
    disabled = {m.group(1) for m in re.finditer(r'"(com\.shinsei[^"]+)" => (?:disabled|true)', dis)}

    print(f"  ロード済み : {', '.join(loaded) if loaded else 'なし（正しい）'}")
    if loaded:
        WARNINGS.append(f"launchd 常駐がロードされている: {', '.join(loaded)}"
                        f"（`launchctl unload` ＋ `launchctl disable` する）")
    for a in agents:
        mark = "無効化済み" if a in disabled else "**有効（再ログインで起動する）**"
        print(f"  plist      : {a} … {mark}")
        if a not in disabled:
            WARNINGS.append(f"{a} が無効化されていない（`launchctl disable gui/$(id -u)/{a}`）")
    cron = subprocess.run(["crontab", "-l"], capture_output=True, text=True).stdout.strip()
    print(f"  cron       : {'あり（中身を確認）' if cron else 'なし（正しい）'}")

    # macOS や Dropbox 自身も *:7000 / *:17500 などでLANに出るが、それは対象外。
    # **このリポジトリのアプリが使う範囲だけ**を見る（3000番台 / 5175 / 8500〜8620）
    def ours(port: int) -> bool:
        return 3000 <= port <= 3010 or 5170 <= port <= 5180 or 8500 <= port <= 8620

    lan = [f"{v}:{k}" for k, v in listening_ports().items()
           if str(v).startswith("*") and ours(k)]
    print(f"  LANに出ている待受（アプリのポートだけ） : {', '.join(lan) if lan else 'なし（正しい）'}")
    if lan:
        WARNINGS.append(f"LANに公開されている待受がある: {', '.join(lan)}（サブPCでは出さない）")


def sync_report(do_fetch: bool) -> None:
    check_git(do_fetch)
    check_versions()
    check_secrets()
    check_autostart()
    print("\n" + "=" * 68)
    if WARNINGS:
        print(f"WARNING: 対応が必要なことが {len(WARNINGS)} 件あります")
        for i, w in enumerate(WARNINGS, 1):
            print(f"  {i}. {w}")
        print("\n※ 勝手に直しません。上を見て、必要なものだけ人が実行してください")
    else:
        print("問題なし: git・バージョン・機密・自動起動のすべてが期待どおりです")
    print("=" * 68)


def main() -> None:
    if "--sync" in sys.argv:
        sync_report("--fetch" in sys.argv)
        return
    filt = next((a for a in sys.argv[1:] if not a.startswith("--")), "")
    live = listening_ports()
    total = {"要作成": 0, "要機密": 0}

    for cat, apps in CATEGORIES.items():
        if filt and filt in CATEGORIES and cat != filt:
            continue
        rows = [scan(a, live) for a in apps if not filt or filt in CATEGORIES or filt in a]
        rows = [r for r in rows if r.get("exists")]
        if not rows:
            continue
        print(f"\n■ {cat}（{len(rows)}本）")
        print(f"  {'アプリ':30}{'種別':9}{'依存':8}{'機密':16}{'待受':14}稼働")
        for r in rows:
            if r["deps"] == "要作成":
                total["要作成"] += 1
            if r["secret"] == "**要**":
                total["要機密"] += 1
            port = f"{r['bind'] or '?'}:{r['port']}" if r["port"] else "-"
            # ツール/ゲームが 0.0.0.0 で待ち受けていたら警告（社内LANへ晒される）
            warn = ""
            if cat != "不動産" and (r["bind"] == "0.0.0.0" or (r["live"] or "").startswith("*")):
                warn = "  ⚠️LAN公開"
            # 本体（worker/LINE/ngrok）がこのPCで動いていたら、二重稼働なので必ず知らせる
            if r["app"] == "chatwork-ai-manager":
                running = _main_pc_only_running(live)
                if running:
                    warn = f"  ⚠️本体がこのPCで起動中（{running}）→ メインPCのみの決まり"
            print(
                f"  {r['app']:30}{r['kind']:9}{r['deps']:8}{r['secret']:16}{port:14}"
                f"{r['live'] or '-'}{warn}"
            )

    print(f"\n依存の作成が必要: {total['要作成']}本 / 機密の受け渡しが必要: {total['要機密']}本")
    print("直すには: ./dev-setup.sh <アプリ名>   （全部なら ./dev-setup.sh --all）")


if __name__ == "__main__":
    main()
