#!/usr/bin/env python3
"""全アプリの「いま触れる状態か」を1画面で出す。

    python3 dev-doctor.py            # 全部
    python3 dev-doctor.py 不動産      # カテゴリで絞る（不動産 / ツール / ゲーム）
    python3 dev-doctor.py baikai     # 名前の一部で絞る

見るのは4点:
  依存    … `.venv` / `node_modules` があるか（**gitで来ないので各PCで作る**）
  機密    … `.env` などが要るアプリか、あるか（**gitで来ない。メインPCから運ぶ**）
  待受    … `run.sh` のバインド先。ツール分類が `0.0.0.0` なら**LANに晒されている**
  起動    … 実際に待ち受けているか（launchd常駐や手動起動の確認）

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


def main() -> None:
    filt = sys.argv[1] if len(sys.argv) > 1 else ""
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
