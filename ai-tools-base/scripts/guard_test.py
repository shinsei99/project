#!/usr/bin/env python3
"""guard.py の判定テスト。

    python3 scripts/guard_test.py

**なぜ要るか**: guard は「外へ出す前の最後の関門」なので、**緩めすぎても厳しすぎても損をする**。
実際に両方やった。

- 厳しすぎ（2026-08-30）… 伏せ字の `◯◯ビル` を建物名と見て止め、**その晩の記事が丸ごと出せなかった**。
  しかもその記事の主題が「置換の誤爆」だった
- 緩すぎ（2026-08-31 に発見）… 許可語の判定が「4文字以上のものを含むか」だったため、
  **`株式会社` を含む `株式会社ヤマダ` まで通っていた**＝法人名の規則が丸ごと効いていなかった

どちらも「動かしてみるまで気づけない」種類なので、境目を表にして固定する。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import guard                                                   # noqa: E402

# (原稿の文, 止めるべきか, なぜ)
CASES: list[tuple[str, bool, str]] = [
    # ── 通すもの（記事に普通に出てよい） ─────────────────────────────
    ("◯◯ビル ××町のオーナーは △△様 です", False, "伏せ字は実在を指さない"),
    ("`◯◯さんビル` を置換した",              False, "伏せ字＋敬称"),
    ("株式会社◯◯",                          False, "法人名も伏せ字なら通す"),
    ("有限会社◯◯商事",                      False, "名前の部分が伏せてある"),
    ("サトウビル",                           False, "例示用の架空名（ALLOW_PART）"),
    ("弊社は株式会社である",                 False, "普通の文。名前ではない"),
    ("株式会社の登記簿を読む",               False, "普通の文"),
    ("株式会社",                             False, "法人格語そのもの"),
    ("ビルドが通らない",                     False, "『ビルド』は建物ではない"),
    ("マンションの管理会社に連絡する",       False, "普通の文"),
    ("<!-- guard-allow: 具体的なモデル名 -->\ngemini-2.0-flash",
                                             False, "申告があれば寿命の語は見逃す"),
    # ── 止めるもの ────────────────────────────────────────────────
    ("ヤマダビル",                           True,  "実在しそうな建物名"),
    ("大京マンション",                       True,  "実在しそうな建物名"),
    ('"ヤマダビル" の件',                    True,  "引用符で囲っても実名は実名"),
    ("株式会社ヤマダ",                       True,  "実在しそうな法人名"),
    ("ヤマダ不動産株式会社",                 True,  "後置の法人名"),
    ("有限会社サンエイ商事",                 True,  "実在しそうな法人名"),
    ("090-1234-5678",                        True,  "個人情報の型"),
    ("<!-- guard-allow: 禁止語リスト -->\n090-1234-5678",
                                             True,  "★個人情報は免除できない"),
    ("<!-- guard-allow: 具体的なモデル名 -->\nヤマダビル",
                                             True,  "★固有名詞は免除できない"),
    ("gemini-2.0-flash",                     True,  "申告が無ければ止める"),
]


def main() -> None:
    ng = 0
    for text, want_block, why in CASES:
        hits = guard.check(Path("dummy.md"), text, [])
        ok = bool(hits) == want_block
        ng += not ok
        mark = "OK  " if ok else "✗ NG"
        print(f"  {mark} {'止める' if want_block else '通す　'}  {why}"
              f"（検知 {len(hits)} 件）")
        if not ok:
            for h in hits:
                print(f"        {h}")
    print(f"── {len(CASES) - ng}/{len(CASES)} 期待どおり")
    sys.exit(1 if ng else 0)


if __name__ == "__main__":
    main()
