#!/usr/bin/env python3
"""各アプリの SESSION_LOG から、まだ記事にしていないネタを拾う。

    ./publish.sh scan            前回のスキャン以降に書かれたものを出す
    ./publish.sh scan --all      全部出す
    ./publish.sh scan --mark     ここまで見た、として記録する（次回はこの後ろだけ出る）
    ./publish.sh scan --limit N  1アプリあたりの表示件数（既定 12・0で全部）

**書いたネタは `drafts/.neta_used.txt` に1行ずつ溜まり、次からは出ない**（日次で回すため）。
`--mark` は日付で線を引くので、同じ日の未消化ぶんまで切り捨ててしまう。日々の重複よけは
そちらではなく used のほうで行う。

CLAUDE.md の決まりで、どのアプリも `SESSION_LOG.md` に
**「### 発生したエラーと解決策」→ 症状 / 原因 / 直し方** を書いている。
つまり**素材は日々の作業で勝手に溜まる**。ここはそれを拾うだけの道具。

拾ったものを書くと決めたら `drafts/NETA.md` に足す（在庫の台帳はあちら一本）。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent      # ai-tools-base/
REPO = ROOT.parent
STATE = ROOT / "drafts" / ".neta_scan.json"
# 書き終えたネタ。1行1件。**gitに入れる**（記事そのものがgitで両PCに渡るので、
# 「もう書いた」の判定も両PCで同じでないと食い違う。端末ごとの .neta_scan.json とは別物）
USED = ROOT / "drafts" / ".neta_used.txt"
DATE = re.compile(r"^##\s*(\d{4}-\d{2}-\d{2})")
HEAD = re.compile(r"^###\s*発生したエラーと解決策")
# エラー節の**先頭の箇条書き**を1件のネタとみなす。
# 以前は「症状」で始まる行だけを拾っていたが、実際のログでその形は3割しかなく
# 7割を取りこぼしていた（2026-08-27 実測 99/293行）。書き方は揃わないので拾う側を広げる。
# ぶら下がりの子項目（字下げ）は details なので拾わない。
ITEM = re.compile(r"^[-*]\s+\S")
LABEL = re.compile(r"^(?:\*\*)?(?:症状|症例)(?:\*\*)?[:：]?\s*")


def entries() -> list[dict]:
    """SESSION_LOG から (アプリ, 日付, 症状の1行) を拾う。"""
    out = []
    for log in sorted(REPO.glob("*/SESSION_LOG.md")):
        app = log.parent.name
        date, in_sec = "", False
        for line in log.read_text(encoding="utf-8", errors="replace").splitlines():
            m = DATE.match(line)
            if m:
                date, in_sec = m.group(1), False
                continue
            if HEAD.match(line):
                in_sec = True
                continue
            if line.startswith("### ") or line.startswith("## "):
                in_sec = False
                continue
            if in_sec and ITEM.match(line):
                text = re.sub(r"^[-*]\s+", "", line)
                text = LABEL.sub("", text)
                text = re.sub(r"\*\*", "", text).strip()
                if len(text) > 8:
                    out.append({"app": app, "date": date, "text": text[:110]})
    return out


NOISE = re.compile(r"[\s`*・「」\"'（）()【】\[\]、。,.:：→…]")


def key(text: str) -> str:
    """同じネタかどうかの判定用。記号と空白を落とした先頭40字で見る。"""
    return NOISE.sub("", text)[:40]


def used() -> set[str]:
    if not USED.exists():
        return set()
    return {key(x) for x in USED.read_text(encoding="utf-8").splitlines()
            if x.strip() and not x.startswith("#")}


def main() -> None:
    items = entries()
    seen = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    since = seen.get("since", "")

    # --used "<行>" … 書き終えたネタを記録する（日次の自動執筆が呼ぶ）
    if "--used" in sys.argv:
        i = sys.argv.index("--used")
        text = " ".join(sys.argv[i + 1:]).strip()
        if not text:
            print("--used のあとに、書いたネタの1行を渡すこと")
            return
        with USED.open("a", encoding="utf-8") as f:
            f.write(text[:110] + "\n")
        print(f"書いたネタとして記録した: {text[:60]}")
        return

    limit = 12
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])

    if "--mark" in sys.argv:
        latest = max((i["date"] for i in items if i["date"]), default="")
        STATE.write_text(json.dumps({"since": latest}, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"ここまで見た、として記録した: {latest}")
        return

    show = items if "--all" in sys.argv else [i for i in items if i["date"] > since]
    done = used()
    skipped = [i for i in show if key(i["text"]) in done]
    show = [i for i in show if key(i["text"]) not in done]
    print(f"── SESSION_LOG から拾ったネタ（全 {len(items)} 件"
          + (f" / {since} より後の {len(show) + len(skipped)} 件" if since and "--all" not in sys.argv else "")
          + (f" / うち書き済み {len(skipped)} 件を除外" if skipped else "")
          + "）──")
    if not show:
        print("  新しいものは無い")
        return

    by_app: dict[str, list[dict]] = {}
    for i in show:
        by_app.setdefault(i["app"], []).append(i)
    for app, xs in sorted(by_app.items(), key=lambda kv: -len(kv[1])):
        print(f"  ■ {app}（{len(xs)}件）")
        for x in sorted(xs, key=lambda x: x["date"], reverse=True)[: (limit or None)]:
            print(f"     {x['date']}  {x['text']}")
    print("\n  書くと決めたものは drafts/NETA.md へ足す（在庫の台帳はあちら一本）")
    print("  見たところまでを記録するなら: ./publish.sh scan --mark")


if __name__ == "__main__":
    main()
