"""実物の画像がどこにも無いカード用に、**デザイン参考の仮画像**を作る。

⚠️ **これは本物ではない。** 同じ系統の別のカードを土台にして、
   ・受賞者の顔写真
   ・受賞者の氏名／順位の行
   ・大会名が入っている本文の行と、下部の帯
   をぼかし、「参考画像」と大きく重ねたもの。**カードの実像ではない。**

なぜ作るのか:
  対象の4枚は**日本一決定戦の入賞者本人にしか渡っていない**うえ、
  **受賞者の顔写真と実名が印刷されている**（例「〈受賞者名〉 2001.8.25」）。
  そのため写真が世に出ておらず、カードショップにも pokumon.com にも画像が無い。
  厳密に言えば入賞者の人数ぶん別のカードなので「その大会の1枚」も存在しない。
  → 図鑑で「だいたいこういう見た目」が分かればよい、という割り切り。

土台に選んだカード（**番号や大会が違う部分は必ずぼかす**）:
  mc/11250 … 2000 ワールドチャレンジ トロピカルメガバトル 日本一決定戦。
             手元にあるのは No.2 なので、**No.2 の表記もぼかす**
  mc/16510-16530 … 2001 バトル★ネオ スプリングロード 日本一決定戦。
             同じ「バトル★ネオ ロード」系のサマーロードを土台にする。
             **番号は一致している**ので、大会名まわりだけぼかす

差し替えるとき: `placeholder_images` テーブルの行を消して build_dex.py を流す。

使い方:
    python placeholder.py
"""

from __future__ import annotations

import os
import sqlite3

from PIL import Image, ImageDraw, ImageFilter, ImageFont

DB = "data/cards.db"
OUT = "data/placeholder"

# (dex_key, 土台の画像, ぼかす範囲[相対座標], 注記)
# 範囲は (左, 上, 右, 下) を 0〜1 の割合で書く
NAME_ROW = (0.04, 0.155, 0.97, 0.225)      # 氏名と「日本一決定戦入賞」の行
PHOTO    = (0.05, 0.225, 0.96, 0.585)      # 受賞者の顔写真が入る枠
# 本文は**大会名が入っている2〜3行目だけ**をぼかす。残り（「ポケモンカード公式
# トーナメント」「…であることをここに認定し、その栄誉をたたえる。」）は
# **どの大会でも同じ定型文**なので隠す意味がない。
#
# ⚠️ 文字の濃さから行を自動検出する実装も試したが**画像ごとに破綻した**
#   （サマー_1 は5行取れたが、サマー_3 は5行を1つの帯として検出、
#    WCトロピカル_2 は本文と別の場所を拾った）。土台は4枚だけなので
#   **画像ごとに実測した固定範囲**のほうが確実。差し替えるときは要再測定。
BODY = (0.10, 0.660, 0.93, 0.755)
FOOTER   = (0.30, 0.955, 0.99, 0.995)      # 下部の「大会名 日付」の帯


def text_lines(im, area):
    """本文の枠の中で、文字がある行の帯を上から順に返す。

    行ごとに「暗い画素の割合」を出し、しきい値を超える帯を1行とみなす。
    目分量で座標を決めると画像ごとにずれるので、こちらで測る。
    """
    w, h = im.size
    l, t, r, b = (int(w*area[0]), int(h*area[1]), int(w*area[2]), int(h*area[3]))
    g = im.convert("L").crop((l, t, r, b))
    W, H = g.size
    px = g.load()
    dark = []
    for y in range(H):
        c = sum(1 for x in range(0, W, 2) if px[x, y] < 110)
        dark.append(c / (W / 2))
    on = [d > 0.03 for d in dark]
    bands, s0 = [], None
    for y, v in enumerate(on):
        if v and s0 is None:
            s0 = y
        elif not v and s0 is not None:
            if y - s0 > H * 0.03:            # 細すぎる帯（罫線等）は行と数えない
                bands.append((s0, y))
            s0 = None
    if s0 is not None and H - s0 > H * 0.03:
        bands.append((s0, H))
    # 枠の縁や罫線が細い帯として混ざるので、**行の高さの中央値の6割未満は捨てる**
    # （実測: 本文の行は43〜45px、枠の縁は20px）
    if bands:
        hs = sorted(b2 - a for a, b2 in bands)
        med = hs[len(hs)//2]
        bands = [x for x in bands if (x[1]-x[0]) >= med * 0.6]
    pad = int(H * 0.012)
    return [(l, t + a - pad, r, t + b2 + pad) for a, b2 in bands]
TITLE    = (0.05, 0.055, 0.96, 0.150)      # No.N TRAINER の見出し（全体）
# 土台の番号が違うときの扱い。**参考画像と明示してあるので、他のカードから
# 見出しのプレートごと借りて重ねる**（ユーザー判断・2026-08-14）。
# 数字1文字だけを差し替える方法も試したが、字形と背景が馴染まず不自然だった。
PLATE_DST = (0.070, 0.052, 0.935, 0.155)   # 土台側の見出しプレート（WCトロピカル_2）
PLATE_SRC = ("data/pokumon/2001サマー_1.jpg", (0.070, 0.052, 0.935, 0.155))  # 借りる「No.1」


def graft_plate(im, dst_rel, src_path, src_rel):
    """別のカードから見出しプレートごと借りて重ねる。**参考画像専用。**"""
    w, h = im.size
    box = (int(w*dst_rel[0]), int(h*dst_rel[1]), int(w*dst_rel[2]), int(h*dst_rel[3]))
    src = Image.open(src_path).convert("RGB")
    sw, sh = src.size
    plate = src.crop((int(sw*src_rel[0]), int(sh*src_rel[1]),
                      int(sw*src_rel[2]), int(sh*src_rel[3])))
    im.paste(plate.resize((box[2]-box[0], box[3]-box[1]), Image.LANCZOS), box)
    return im


JOBS = [
    ("mc/11250", "data/pokumon/2000WCトロピカル_2.jpg",
     [NAME_ROW, PHOTO, BODY, FOOTER],
     "土台は No.2。**別カードから見出しプレートごと借りて重ねた**（参考画像なので可、と判断）"),
    ("mc/16510", "data/pokumon/2001サマー_1.jpg",
     [NAME_ROW, PHOTO, BODY, FOOTER],
     "土台はサマーロードの No.1。番号は一致。大会名まわりをぼかした"),
    ("mc/16520", "data/pokumon/2001サマー_2.jpg",
     [NAME_ROW, PHOTO, BODY, FOOTER], "同上（No.2）"),
    ("mc/16530", "data/pokumon/2001サマー_3.jpg",
     [NAME_ROW, PHOTO, BODY, FOOTER], "同上（No.3）"),
]


def font(size):
    for p in ("/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
              "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/Library/Fonts/Arial Unicode.ttf"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()


def make(src, boxes, graft=False):
    im = Image.open(src).convert("RGB")
    w, h = im.size
    if graft:
        im = graft_plate(im, PLATE_DST, PLATE_SRC[0], PLATE_SRC[1])
    for (l, t, r, b) in boxes:
        box = ((int(w*l), int(h*t), int(w*r), int(h*b))
               if max(l, t, r, b) <= 1 else (int(l), int(t), int(r), int(b)))
        part = im.crop(box).filter(ImageFilter.GaussianBlur(max(6, w // 45)))
        im.paste(part, box)
    # 「参考画像」と分かるように帯を重ねる（本物と取り違えないため）
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    f = font(max(28, w // 11))
    txt = "参考画像"
    tw = d.textbbox((0, 0), txt, font=f)[2]
    for y in (int(h*0.34), int(h*0.70)):
        d.text(((w - tw)//2, y), txt, font=f, fill=(220, 30, 30, 120))
    d.rectangle([0, 0, w-1, h-1], outline=(220, 30, 30, 200), width=max(3, w//120))
    return Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")


def main():
    con = sqlite3.connect(DB, timeout=300)
    con.executescript("""
    CREATE TABLE IF NOT EXISTS placeholder_images (
      dex_key TEXT PRIMARY KEY,
      base    TEXT,      -- 土台にしたカードの画像
      local   TEXT,
      note    TEXT
    );""")
    os.makedirs(OUT, exist_ok=True)
    n = 0
    for key, base, boxes, note in JOBS:
        if not os.path.exists(base):
            print(f"{key} 土台が無い: {base}")
            continue
        row = con.execute("SELECT name FROM dex WHERE key = ?", (key,)).fetchone()
        p = os.path.join(OUT, key.replace("/", "_") + ".jpg")
        make(base, boxes, graft=(key == "mc/11250")).save(p, quality=92)
        con.execute("""INSERT OR REPLACE INTO placeholder_images
                       (dex_key, base, local, note) VALUES (?,?,?,?)""",
                    (key, base, p, note))
        n += 1
        print(f"{key} {row[0] if row else '?'} ← {os.path.basename(base)}  {note}")
    con.commit()
    print(f"\n作成 {n}枚（**参考画像**。本物ではない）")
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
