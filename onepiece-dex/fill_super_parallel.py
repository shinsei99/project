"""
「スーパーパラレル（コミパラ）」系のレアリティを補う。

**公式サイトはこの区分を持っていない。** OP17-005 は通常も `_p1` も `_p2` も一律 `SR` で、
HTMLにも差が無い（2026-08-23に実物で確認）。だが実物の `_p2` は枠なし・背景が原作コマの
**スーパーパラレル**で、相場も扱いもまったく違う。公式データだけでは絞り込めないので、
外部の一覧を典拠にして補う。

  典拠: https://tier-one-onepiece.jp/blog/manga-rare-card-list/

**型番しか書いていない一覧から、どの別イラスト（_p2 など）かをどう決めるか。**
一覧のカード画像を落としてきて、手元の同じ型番の画像すべてと**見た目で照合**する
（32×45のグレースケールに落として正規化し、二乗誤差が一番小さいものを採る）。
実測で分離は明確: OP17-005 は `_p2` が 0.054、次点の `_p1` が 1.645。

**1つの型番に2枚当たることがある。** 同じ絵柄が別の弾で再録されるため
（EB01-006 は EB-01 の `_r1` と PRB-01 の `_p2` がどちらもコミパラで、
距離は 0.245 と 0.260 でほぼ同じ）。近いものは**まとめて採る**。

結果は `data/super_parallel.json` に置く。**人が見て直せる形**にしてあり、
`build_dex.py` がこれを読んでレアリティを差し替える。ポケカ図鑑の
`pack_truth.json`（手で確かめた事実を書き留めるファイル）と同じ扱い。

使い方:
    python fill_super_parallel.py            # 取得 → 照合 → JSON書き出し
    python fill_super_parallel.py --show     # 既存のJSONを表示するだけ
"""

from __future__ import annotations

import glob
import html
import json
import os
import re
import sys
import urllib.request

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
IMG = os.path.join(HERE, "data", "img")
REF = os.path.join(HERE, "data", "sp_ref")
OUT = os.path.join(HERE, "data", "super_parallel.json")
SRC = "https://tier-one-onepiece.jp/blog/manga-rare-card-list/"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Referer": "https://tier-one-onepiece.jp/"}

# ファイル名の略号 → レアリティ名。見出しのほうが細かいので、見出しを優先する
BY_SUFFIX = {"sp": "スーパーパラレル", "gsp": "ゴールドスーパーパラレル",
             "rsp": "レッドスーパーパラレル", "slp": "リーダースーパーパラレル"}
# 見出しに出てくる名前（「〜とは」の節に置かれた画像はその種類）
BY_HEADING = ["ゴールドスーパーパラレル", "レッドスーパーパラレル",
              "リーダースーパーパラレル", "海賊団スーパーパラレル",
              "神の騎士団スーパーパラレル", "スーパーパラレル"]

# 照合のしきい値。best の2倍＋0.05 までを同じ絵とみなす（再録の拾い漏れを防ぐ）。
# 0.6 を超えるものは別の絵なので採らない
NEAR = 0.6


def fetch(url: str) -> bytes:
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
        return r.read()


def parse(page: str):
    """見出しとカード画像を**文書に出てくる順**に拾い、各画像に直前の見出しを付ける。

    節ごとに種類が分かれている（「ゴールドスーパーパラレルとは」の節にある画像は
    ゴールドスーパーパラレル）ので、見出しを見ないと種類を取り違える。
    """
    i = page.find("スーパーパラレル（コミパラ）一覧")
    page = page[i:] if i > 0 else page
    ev = []
    for m in re.finditer(r"<h([234])[^>]*>(.*?)</h\1>", page, re.S | re.I):
        ev.append((m.start(), "H",
                   re.sub(r"<[^>]+>", "", html.unescape(m.group(2))).strip()))
    pat = (r"(https?://[^\"']*wp-content/uploads/((?:op|eb|prb|st)\d{2}-\d{3})"
           r"([a-z]*)((?:-[a-z0-9]+)*?)(?:-\d+x\d+)?\.(?:webp|png|jpg))")
    for m in re.finditer(pat, page, re.I):
        ev.append((m.start(), "I", (m.group(2).upper(), m.group(3).lower(),
                                    (m.group(4) or "").strip("-"), m.group(1))))
    ev.sort(key=lambda x: x[0])
    head, out = None, {}
    for _, kind, v in ev:
        if kind == "H":
            head = v
        elif head:
            code, suf, extra, url = v
            key = (code, suf, extra)
            if key not in out:
                out[key] = (head, url)
    return out


def rarity_of(head: str, suf: str) -> str:
    for name in BY_HEADING:
        if head.startswith(name):
            return name
    return BY_SUFFIX.get(suf, "スーパーパラレル")


def sig(path_or_bytes):
    """見た目の指紋。32×45のグレースケールを平均0・分散1に正規化したもの。

    大きさも明るさも違う画像どうしを比べるため。色は使わない
    （同じ絵の金版・赤版があるので、色で比べると別物になってしまう）。
    """
    im = Image.open(path_or_bytes if not isinstance(path_or_bytes, bytes)
                    else __import__("io").BytesIO(path_or_bytes))
    a = np.asarray(im.convert("L").resize((32, 45)), dtype=float)
    return (a - a.mean()) / (a.std() + 1e-6)


def main() -> None:
    if "--show" in sys.argv:
        for k, v in json.load(open(OUT)).items():
            print(f"{k:16s} {v['rarity']:16s} 距離{v['distance']:.3f}")
        return

    os.makedirs(REF, exist_ok=True)
    found = parse(fetch(SRC).decode("utf-8", "replace"))
    print(f"典拠の一覧 {len(found)}件\n")

    result, missing, ambiguous = {}, [], []
    for (code, suf, extra), (head, url) in sorted(found.items()):
        rarity = rarity_of(head, suf)
        cands = sorted(glob.glob(os.path.join(IMG, f"{code}*.png")))
        # 同じ型番のものだけを候補にする（OP17-005 に OP17-0050 は入らない）
        cands = [c for c in cands
                 if re.fullmatch(re.escape(code) + r"(_[a-z]\d+)?",
                                 os.path.basename(c)[:-4])]
        if not cands:
            missing.append((code, rarity, "手元にこの型番が無い"))
            continue
        ref_file = os.path.join(REF, re.sub(r"[^\w.-]", "_",
                                            f"{code}_{suf}_{extra}") + ".img")
        if not os.path.exists(ref_file):
            try:
                open(ref_file, "wb").write(fetch(url))
            except Exception as e:
                missing.append((code, rarity, f"参照画像が取れない: {e}"))
                continue
        try:
            ref = sig(ref_file)
        except Exception as e:
            missing.append((code, rarity, f"参照画像が読めない: {e}"))
            continue

        scores = sorted((float(np.mean((ref - sig(c)) ** 2)),
                         os.path.basename(c)[:-4]) for c in cands)
        best = scores[0][0]
        hits = [(d, k) for d, k in scores if d <= min(best * 2 + 0.05, NEAR)]
        if best > NEAR:
            missing.append((code, rarity, f"似た絵が無い（最小{best:.2f}）"))
            continue
        if len(hits) > 1:
            ambiguous.append((code, rarity, [k for _, k in hits]))
        for d, k in hits:
            # 同じカードに2つの種類が当たったら、より限定的なほう（金・赤など）を残す
            if k in result and result[k]["rarity"] != "スーパーパラレル":
                continue
            result[k] = {"code": code, "rarity": rarity, "distance": round(d, 4),
                         "heading": head, "ref": url}
        mark = "  ← 2枚に当たった" if len(hits) > 1 else ""
        print(f"  {code:10s} {rarity:16s} → "
              + " ".join(k for _, k in hits) + f"  距離{best:.3f}{mark}")

    json.dump(result, open(OUT, "w"), ensure_ascii=False, indent=1, sort_keys=True)
    print(f"\n書き出し {len(result)}枚 → {os.path.relpath(OUT, HERE)}")
    by = {}
    for v in result.values():
        by[v["rarity"]] = by.get(v["rarity"], 0) + 1
    for r, n in sorted(by.items(), key=lambda x: -x[1]):
        print(f"  {r:20s} {n}枚")
    if ambiguous:
        print(f"\n1つの型番に2枚当たったもの {len(ambiguous)}件"
              "（同じ絵が別の弾で再録されている。両方ともコミパラなので両方に付ける）")
        for code, r, ks in ambiguous:
            print(f"  {code}  {r}  {' / '.join(ks)}")
    if missing:
        print(f"\n付けられなかったもの {len(missing)}件")
        for code, r, why in missing:
            print(f"  {code}  {r}  … {why}")


if __name__ == "__main__":
    main()
