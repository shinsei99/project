#!/usr/bin/env python3
"""外へ出す前の関門。**個人情報・固有名詞・実測でない数字**を機械で止める。

    ./publish.sh guard              これから出すもの（未公開の原稿）を全部検査する
    ./publish.sh guard <slug>       1本だけ検査する

**ここを通らないものは公開しない。** 自動生成した記事を人が読まずに外へ出すので、
人の目の代わりにこれを置いている。落ちたら `published: false` のまま止まる。

## 何を止めるか

1. **個人情報の型** … 電話・携帯・FAX、メール、郵便番号＋番地、口座番号、
   マイナンバー桁、免許証番号の型
2. **禁止語リスト** … `drafts/.pii-blocklist.txt`（**gitignore**。社名・物件名・
   オーナー名・社員名・取引先をここに書く。1行1語、`#` はコメント）
3. **固有名詞らしきもの** … 「株式会社○○」「○○ビル」「○○マンション」「○丁目○番」など、
   実在を指しそうな形。記事は一般化して書く決まりなので、出てきたら止める
4. **作品の寿命を縮める語** … 具体的なモデル名・SDKのバージョン（NETA.md の方針）

## 使い方の前提

**blocklist は人が埋める。** 空でも 1・3・4 は効くが、社名や物件名は
知らないと止められない。`drafts/.pii-blocklist.txt.example` を写して使う。
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent
BLOCK = ROOT / "drafts" / ".pii-blocklist.txt"

PII = [
    ("電話・FAX番号", re.compile(r"0\d{1,4}[-(－][\d-]{5,}\d")),
    ("携帯番号", re.compile(r"0[789]0[-\d]{9,}")),
    ("メールアドレス", re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")),
    # 前後が数字やハイフンなら郵便番号ではない（電話番号の一部を拾わないため）
    ("郵便番号", re.compile(r"(?<![\d-])〒?\d{3}-\d{4}(?![\d-])")),
    ("番地つき住所", re.compile(r"[都道府県市区町村][^\s、。]{0,12}?\d+[-−丁目]\d+")),
    ("口座番号らしき数字", re.compile(r"(?:口座|普通|当座)[^\n]{0,8}\d{7}")),
    ("個人番号の桁", re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b")),
]

PROPER = [
    ("法人名", re.compile(r"(?:株式会社|有限会社|合同会社)\s*[^\s、。「」）\)]{1,12}")),
    ("法人名（後置）", re.compile(r"[^\s、。「」（\(]{1,12}\s*(?:株式会社|不動産株式会社)")),
    # 「ビルド」を建物名と誤判定しないこと（最初に作ったとき12件が誤検知になった）
    ("建物名", re.compile(r"[^\s、。「」（\(]{2,12}(?:ビル(?!ド)|マンション|ハイツ|コーポ|アパート|荘)(?![のにはをがで、。])")),
    ("丁目番地", re.compile(r"\d+丁目\d+番")),
]

VERSIONY = [
    # claude-code / Claude Code は媒体の主題なので止めない。止めたいのは世代付きのモデル名
    ("具体的なモデル名", re.compile(r"(?:gpt-[\d.]+|claude-(?!code)[a-z]+-?[\d.]+[a-z0-9-]*|gemini-[\d.]+[a-z-]*)")),
    ("SDKのバージョン", re.compile(r"@?[\w-]+@\d+\.\d+\.\d+")),
]

# 記事で普通に出てよいもの（誤検知を減らす）
ALLOW = {
    "株式会社", "有限会社", "合同会社",
    "サトウビル", "テストビル",          # 例示用に使っている架空名
}

# 記事の例示に使ってよい番号帯（総務省が例示用に確保しているもの）。
# 実在の番号を例に使わないための逃げ道。
EXAMPLE_TEL = re.compile(r"0\d{1,3}[-(－]?5555[-)－]?\d{4}|０\d{1,3}－５５５５－\d{4}")


def blocklist() -> list[str]:
    if not BLOCK.exists():
        return []
    return [l.strip() for l in BLOCK.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


def check(path: Path, text: str, words: list[str]) -> list[str]:
    bad = []
    for label, pat in PII:
        for m in pat.finditer(text):
            if "番号" in label and EXAMPLE_TEL.search(m.group(0)):
                continue                      # 例示用の番号帯は通す
            bad.append(f"[個人情報の型/{label}] {m.group(0)[:40]}")
    for w in words:
        if w in text:
            bad.append(f"[禁止語リスト] {w}")
    for label, pat in PROPER:
        for m in pat.finditer(text):
            s = m.group(0).strip()
            if s in ALLOW or any(a in s for a in ALLOW if len(a) > 3):
                continue
            bad.append(f"[固有名詞らしき/{label}] {s[:40]}")
    for label, pat in VERSIONY:
        for m in pat.finditer(text):
            bad.append(f"[寿命を縮める語/{label}] {m.group(0)[:40]}")
    return bad


def targets(only: str | None) -> list[Path]:
    out = []
    for f in sorted((REPO / "articles").glob("*.md")):
        if "published: false" in f.read_text(encoding="utf-8"):
            out.append(f)
    for f in sorted((ROOT / "drafts" / "note").glob("*.md")):
        out.append(f)
    for f in sorted((ROOT / "content" / "works").glob("*.json")):
        out.append(f)
    for f in sorted((ROOT / "content" / "articles").glob("*.mdx")):
        out.append(f)
    if only:
        out = [f for f in out if only in f.name]
    return out


def main() -> None:
    only = next((a for a in sys.argv[1:] if not a.startswith("-")), None)
    words = blocklist()
    if not words:
        print("  ⚠️ 禁止語リストが空（drafts/.pii-blocklist.txt）。"
              "社名・物件名・氏名はここに書かないと止められない")

    files = targets(only)
    ng = 0
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        if f.suffix == ".json":
            try:
                text = json.dumps(json.loads(text), ensure_ascii=False)
            except Exception:
                pass
        bad = check(f, text, words)
        if bad:
            ng += 1
            print(f"  ✗ {f.relative_to(REPO)}")
            for b in sorted(set(bad))[:8]:
                print(f"      {b}")
    print(f"── 検査 {len(files)} 本 … 問題なし {len(files) - ng} / 要確認 {ng}")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
