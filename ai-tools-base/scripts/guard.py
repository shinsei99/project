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
#
# ★2種類ある（2026-08-31に分けた）。混ぜていたせいで**法人名の規則が丸ごと効いていなかった**。
#   `ALLOW_EXACT` … その語そのものなら通す。「株式会社」単独は普通に本文へ出てよい
#   `ALLOW_PART`  … 一部に含まれていれば通す。例示用の架空名
#
#   もとは1つの集合を「完全一致 または 4文字以上のものが含まれる」で見ていた。
#   「株式会社」は4文字なので、**`株式会社ヤマダ` も「株式会社を含む」で通っていた**
#   （＝法人名は何を書いても止まらない）。実測して気づいた。
ALLOW_EXACT = {"株式会社", "有限会社", "合同会社", "不動産株式会社"}
ALLOW_PART = {"サトウビル", "テストビル"}          # 例示用に使っている架空名

# ★伏せ字だけで出来た名前は通す（2026-08-31）。
#
#   記事は「固有名詞を伏せて書く」決まりなので、原稿には `◯◯ビル` `△△マンション`
#   `◯◯さんビル` のような伏せ字が普通に出てくる。これは実在を指していないので止める理由が無い。
#   2026-08-30 の自動執筆（name-substitution-misfires）が `◯◯ビル` で止まり、
#   **記事が1本まるごと出せなくなった**。しかもその記事の主題が「置換の誤爆」だった。
#
#   判定は「三点セット（伏せ字・敬称・建物や法人を表す語）を取り除いたら何も残らないか」。
#   `サトウビル` は `サトウ` が残るので今までどおり止まる。
MASK_CHARS = set("◯○〇◎●△▲▽▼□■×✕✖＊*？?")
TRIM_CHARS = "`\"'「」『』（）()　 \t・ー－-"
_TRIGGER = re.compile(r"(?:ビル|マンション|ハイツ|コーポ|アパート|荘|"
                      r"不動産株式会社|株式会社|有限会社|合同会社)")
_HONORIFIC = re.compile(r"(?:さん|様|氏|くん|ちゃん)")


def is_masked(s: str) -> bool:
    """「◯◯ビル」「△△さんビル」「株式会社◯◯」のように、名前の部分が伏せてあるか。

    ★飾り記号（引用符・バッククォート）は先に落とす。落とさずに「伏せ字を含むか」で
      見ると、`"ヤマダビル"` のような**引用符つきの実名まで通ってしまう**。
    """
    rest = _HONORIFIC.sub("", _TRIGGER.sub("", s)).strip(TRIM_CHARS)
    return not rest or rest[0] in MASK_CHARS


# 「弊社は株式会社である」「株式会社の登記簿」のような**普通の文**を名前と間違えないための判定。
# 日本語の会社名は漢字・カタカナ・英字で始まる。法人格語の直後（または直前）が
# **ひらがな**なら、それは名前ではなく文の続き。
_HIRAGANA = re.compile(r"[ぁ-ん]")
_CORP = re.compile(r"(?:不動産株式会社|株式会社|有限会社|合同会社)")


def is_generic_corporate(s: str) -> bool:
    """法人格語を含むが、名前ではない普通の文か。"""
    m = _CORP.search(s)
    if not m:
        return False
    before, after = s[:m.start()].strip(TRIM_CHARS), s[m.end():].strip(TRIM_CHARS)
    if not before and not after:
        return True                                  # 「株式会社」単独
    if after and _HIRAGANA.match(after[0]):
        return True                                  # 株式会社**である**
    if before and _HIRAGANA.match(before[-1]):
        return True                                  # 弊社**は**株式会社
    return False

# 記事の例示に使ってよい番号帯（総務省が例示用に確保しているもの）。
# 実在の番号を例に使わないための逃げ道。
EXAMPLE_TEL = re.compile(r"0\d{1,3}[-(－]?5555[-)－]?\d{4}|０\d{1,3}－５５５５－\d{4}")


# ★1本だけ例外を認める仕組み（2026-08-31）。
#
#   原稿に `<!-- guard-allow: 具体的なモデル名 -->` と書いておくと、その項目だけ見逃す。
#   **免除できるのは「寿命を縮める語」だけ**。個人情報・禁止語・固有名詞は**免除できない**
#   （原稿を書くのは機械なので、機械が自分で個人情報の関門を外せてはいけない）。
#
#   なぜ要るか: 「モデルにもSDKにも寿命がある」という記事は、**モデル名そのものが主題**で、
#   `gemini-2.0-flash is no longer available` という実際のエラーが証拠になっている。
#   この規則は「うっかり版を固定して書く」のを止めるためのもので、こういう記事は対象外。
WAIVABLE = {"具体的なモデル名", "SDKのバージョン"}
WAIVER_RE = re.compile(r"guard-allow:\s*([^\n>]+)")


def waived_labels(text: str) -> set[str]:
    """原稿が自分で申告した免除項目のうち、免除してよいものだけ返す。"""
    out: set[str] = set()
    for m in WAIVER_RE.finditer(text):
        for w in re.split(r"[,、\s]+", m.group(1).strip()):
            if w in WAIVABLE:
                out.add(w)
    return out


def blocklist() -> list[str]:
    if not BLOCK.exists():
        return []
    return [l.strip() for l in BLOCK.read_text(encoding="utf-8").splitlines()
            if l.strip() and not l.startswith("#")]


# Zenn のファイル名（＝slug）の決まり。半角英数字・ハイフン・アンダースコアの12〜50文字。
# ★1本でも違反があると **Zenn はデプロイ全体を中断する**（2026-08-28に実際に起きた）。
#   `a4-one-page`（11文字）が1本混ざっていただけで、予約投稿25本が丸ごと届かず、
#   Zennへの公開が1日以上止まっていた。しかも Zenn側の画面を見るまで気づけない
#   （手元では push も成功し、note と本体サイトは普通に出ていた）。
SLUG_RE = re.compile(r"^[a-z0-9_-]{12,50}$")


def check_slug(path: Path) -> list[str]:
    """記事のファイル名が Zenn の決まりに合っているか。

    articles/ と **待機場所（drafts/zenn_pending）** の .md を見る。
    待機場所のファイル名はそのまま articles/ へ移る＝そのままZennのURLになるので、
    出す晩ではなく**書いた晩に**気づけるほうがよい。
    """
    if path.suffix != ".md" or path.parent.name not in ("articles", "zenn_pending"):
        return []
    slug = path.stem
    if SLUG_RE.match(slug):
        return []
    return [f"[Zennのslug] 「{slug}」({len(slug)}文字) は不正。"
            "半角英数字・ハイフン・アンダースコアの12〜50文字にすること。"
            "★1本でもあるとZennのデプロイ全体が止まる"]


def check(path: Path, text: str, words: list[str]) -> list[str]:
    bad = check_slug(path)
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
            if s in ALLOW_EXACT or any(a in s for a in ALLOW_PART):
                continue
            if is_masked(s):            # 「◯◯ビル」など伏せ字の名前は実在を指さない
                continue
            if is_generic_corporate(s):  # 「弊社は株式会社である」は名前ではない
                continue
            bad.append(f"[固有名詞らしき/{label}] {s[:40]}")
    waived = waived_labels(text)
    for label, pat in VERSIONY:
        if label in waived:
            continue
        for m in pat.finditer(text):
            bad.append(f"[寿命を縮める語/{label}] {m.group(0)[:40]}")
    return bad


def targets(only: str | None) -> list[Path]:
    out = []
    # ★slug検査は published の値に関係なく全記事に効かせる（2026-08-28）。
    #   以前は「published: false のものだけ」を対象にしていたため、
    #   予約中・公開済みのファイル名が不正でも気づけなかった。
    #   Zenn は1本でも不正なファイル名があると**デプロイ全体を中断する**ので、
    #   すでに published: true になっている記事こそ見ないといけない。
    for f in sorted((REPO / "articles").glob("*.md")):
        if "published: false" in f.read_text(encoding="utf-8"):
            out.append(f)
        elif not SLUG_RE.match(f.stem):
            out.append(f)          # 中身は通っている前提。ファイル名だけ引っかかる
    # ★待機場所も検査する（2026-08-31）。記事は書いた晩に articles/ から待機場所へ移るので、
    #   ここを見ないと **Zennへ出す本文が検査されない期間**ができる
    #   （zenn-daily は出す直前に `guard <slug>` を呼ぶが、そのとき本文はまだ待機場所にある）。
    for f in sorted((ROOT / "drafts" / "zenn_pending").glob("*.md")):
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
