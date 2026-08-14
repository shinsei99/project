"""トロフィーカード（No.Xトレーナー）の絵を、**推定で**当てる。

⚠️ **ここに入っているのは全部「推定」。確証ではない。**
   新しい資料が出たら差し替えること。該当行は
   `SELECT dex_key, guess, confidence FROM trophy_guess` で引ける。

■ 分かっていること（2026-08-14 に調べた）

  ・**カード本体に大会の地区名は入っていない。** マンダラケの出品
    「第2回公式トーナメントシリーズ カメックスメガバトル 関西大会 優勝
     1998年8月22日」の実物写真で確認した。地区名はアクリル盾の金属プレート側で、
    中のカードは dex の `puromo01_042` とまったく同じ。
    → **同じシリーズなら地区が違っても同じカード。**

  ・ただし**シリーズが違えば別のカード**。絵柄は4系統ある
    （sataku009 氏のブログ「レアカードあれこれ 魔界編」の分類とも一致）:

      ピカチュウ版        トロフィーを掲げるピカチュウ。
                        「第1回」「第2回…日本一決定戦への参加権」の2種。dex にあり
      トロピカルメガバトル版  ナッシー＋TROPICAL MEGA BATTLE ロゴ
      シークレットスーパーバトル版  黒地＋SECRET SUPER BATTLE ロゴ
      neo版             女の子／男の子とポケモンのイラスト。`No.N TRAINER` 表記。
                        **これは1つの大会のカードではない。** 同じ絵柄が
                        「ワールドチャレンジ -トロピカルメガバトル-」
                        「ワールドチャレンジ -シークレットスーパーバトル-」
                        「バトル★ネオ-スプリングロード」で使い回されており、
                        **大会名は文面に書いてある**。男の子版には
                        **受賞者名と地区まで印字**される（例「〈受賞者名〉 北海道大会ジュニア2位入賞」）

  ・**どの絵柄にも予選版と本選版がある。文面で見分ける。**
      予選版 … 「…日本一決定戦への参加権があることを証明する。」の行がある
      本選版 … その行が無く「…であることをここに認定し、その栄誉をたたえる。」だけ
    ENNDALGAMES の出品で確認（8426＝予選の黒地版 / 22683＝本選の女の子版）

■ 対応づけの根拠（マイカのカードIDは発売順）

  960-1050  … 真ん中の 1020 が「トロピカルウインド（トロピカルメガバトル
              決勝トーナメント出場記念）」。**前後を挟んでいるので1999年の
              トロピカルメガバトル関連**。ただし**手元の3枚が予選版と本選版の
              混在**で、3組の内訳も不明（確からしさ 中）
  16510-16530 … 2001年。黒地SECRET SUPER BATTLEロゴの予選版で3枚が整合（確からしさ 高）
  11250-11270 / 16550-16570 … **取り下げた**（下の「埋められないもの」参照）

■ 埋められないもの（2026-08-14 時点）

  ・mc/11250-11270（2000年）… 大会が特定できない
  ・mc/16550-16570（2001年）… ワールドチャレンジ -シークレットスーパーバトル-（本選）
    とみられるが、**No.1 の画像しか無い**（No.2/No.3 が見つからない）

使い方:
    python trophy.py --dry-run
    python trophy.py
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import time
import urllib.request

from PIL import Image, ImageFilter

DB = "data/cards.db"
IMG_DIR = "data/pokepedia"
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
BASE = "https://www.pokepedia.fr/images/"

# 絵柄 → ローカルのファイル名（IMG_DIR からの相対）
# 出所: pokumon.com（大会名と年がスラッグに入っていて確実）／Poképédia
# **1枚ずつ開いて絵柄と文面を確かめたものだけ**を載せている。
DESIGNS = {
    # 1999 チャレンジロード A ＝ ナッシー＋TROPICAL MEGA BATTLE ロゴ・**参加権の行なし**（本選版）
    ("99ナッシー本選", 1): "../pokumon/1999チャレンジA_1.jpg",
    ("99ナッシー本選", 2): "../pokumon/1999チャレンジA_2.jpg",
    ("99ナッシー本選", 3): "../pokumon/1999チャレンジA_3.jpg",
    # 1999 チャレンジロード B ＝ 黒地 SECRET SUPER BATTLE ロゴ・**参加権あり**（予選版）
    ("99黒地予選", 1): "../pokumon/1999チャレンジB_1.jpg",
    ("99黒地予選", 2): "../pokumon/1999チャレンジB_2.jpg",
    ("99黒地予選", 3): "../pokumon/1999チャレンジB_3.jpg",
    # ナッシー・**参加権あり**（トロピカルメガバトル日本一決定戦への参加権）
    ("99ナッシー予選", 1): "トロピカルメガバトル_1.png",
    ("99ナッシー予選", 2): "トロピカルメガバトル_2.png",
    ("99ナッシー予選", 3): "トロピカルメガバトル_3.png",
    # 2000 ワールドチャレンジ トロピカルメガバトル 日本一決定戦（No.1 は pokumon に画像なし）
    ("00WCトロピカル", 2): "../pokumon/2000WCトロピカル_2.jpg",
    ("00WCトロピカル", 3): "../pokumon/2000WCトロピカル_3.jpg",
    # 2001 バトル★ネオ サマーロード 日本一決定戦（**受賞者の顔写真と実名が印刷**されている）
    ("01サマーロード", 1): "../pokumon/2001サマー_1.jpg",
    ("01サマーロード", 2): "../pokumon/2001サマー_2.jpg",
    ("01サマーロード", 3): "../pokumon/2001サマー_3.jpg",
}

# (dex_key, 絵柄, No., 確からしさ, 根拠)
#
# **年代でしか当てられない。** マイカは大会名を持っていないので、
# カードIDの位置（＝発売順）と、pokumon.com のスラッグに入っている年を突き合わせる。
# **同じ年に複数の大会があるところは、どれがどれか決める材料が無い。**
GUESS = [
    ("mc/960",  "99ナッシー本選", 1, "中", "1999年ブロック。1020 トロピカルウインドを挟む位置。年は確かだが3組の並び順の根拠は無い"),
    ("mc/970",  "99ナッシー本選", 2, "中", "同上"),
    ("mc/980",  "99ナッシー本選", 3, "中", "同上"),
    ("mc/990",  "99黒地予選", 1, "中", "1999年ブロック。黒地は pokumon で challenge-road-1999 に分類されている"),
    ("mc/1000", "99黒地予選", 2, "中", "同上"),
    ("mc/1010", "99黒地予選", 3, "中", "同上"),
    ("mc/1030", "99ナッシー予選", 1, "低", "1999年ブロックの3組目。ナッシーの参加権あり版を当てたが並び順の根拠は無い"),
    ("mc/1040", "99ナッシー予選", 2, "低", "同上。**手元の No.2/No.3 は参加権なし版**なので厳密には不整合"),
    ("mc/1050", "99ナッシー予選", 3, "低", "同上"),
    ("mc/11260", "00WCトロピカル", 2, "中", "2000年ブロック。直前が「トロピカルメガバトル in ハワイ 参加記念」なので大会が合う"),
    ("mc/11270", "00WCトロピカル", 3, "中", "同上"),
    ("mc/16550", "01サマーロード", 1, "低", "2001年ブロックの2組目。スプリングロードとサマーロードのどちらかで決め手が無い"),
    ("mc/16560", "01サマーロード", 2, "低", "同上"),
    ("mc/16570", "01サマーロード", 3, "低", "同上"),
]

# --- 当てられないもの（2026-08-14 時点） -------------------------------------
# mc/11250        … 2000 ワールドチャレンジ トロピカルの **No.1 が pokumon にも無い**
# mc/16510-16530  … 2001年ブロックの1組目。ネオスプリングロードとみられるが
#                   pokumon にあるのは No.2 だけ（しかも165x226と極小）
#
# ⚠️ **サマーロード／スプリングロードは受賞者の顔写真と実名が印刷される**
#   （例「〈受賞者名〉 日本一決定戦入賞 2001.8.25」）。受賞者ごとに別物なので、
#   1枚を代表画像として当てること自体が妥当か要検討。

# 受賞者の**顔写真と実名が印刷されているカード**は、そのまま図鑑に置かない。
# 当時子どもだった方の顔と本名なので、氏名の行と顔だけをぼかした複製を使う。
# 大会名・順位・日付は情報として残す。
PHOTO_DESIGNS = ("00WCトロピカル", "01サマーロード")
MASK_DIR = "data/pokumon_masked"
MASK_NAME = (0.04, 0.150, 0.97, 0.230)     # 氏名と「日本一決定戦入賞」の行
MASK_FACE = (0.36, 0.250, 0.66, 0.470)     # イラスト枠の中央（顔のあたり）


def mask_personal(src):
    """氏名の行と顔だけをぼかした複製を作り、そのパスを返す。"""
    os.makedirs(MASK_DIR, exist_ok=True)
    out = os.path.join(MASK_DIR, os.path.basename(src))
    if os.path.exists(out):
        return out
    im = Image.open(src).convert("RGB")
    w, h = im.size
    for rel in (MASK_NAME, MASK_FACE):
        box = (int(w*rel[0]), int(h*rel[1]), int(w*rel[2]), int(h*rel[3]))
        im.paste(im.crop(box).filter(ImageFilter.GaussianBlur(max(6, w // 40))), box)
    im.save(out, quality=92)
    return out


def setup(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS trophy_guess (
      dex_key    TEXT PRIMARY KEY,
      guess      TEXT,      -- 当てた絵柄
      card_no    INTEGER,   -- No.1 / 2 / 3
      confidence TEXT,      -- 高 / 中 / 低
      reason     TEXT,
      url        TEXT,
      local      TEXT
    );
    """)
    con.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    con = sqlite3.connect(DB, timeout=300)
    setup(con)
    n = 0
    for key, design, no, conf, reason in GUESS:
        fn = DESIGNS[(design, no)]
        local = os.path.normpath(os.path.join(IMG_DIR, fn))
        url = ""
        row = con.execute("SELECT name FROM dex WHERE key = ?", (key,)).fetchone()
        if not row or row[0] != f"No.{no}トレーナー":
            print(f"{key} 名前が合わない: {row[0] if row else '行なし'} / 期待 No.{no}トレーナー")
            continue
        print(f"{key} {row[0]} ← {design} No.{no}（確からしさ {conf}）")
        if a.dry_run:
            continue
        if not os.path.exists(local):
            print(f"    画像が無い: {local}")
            continue
        if design in PHOTO_DESIGNS:
            local = mask_personal(local)      # 受賞者の顔と実名をぼかす
        n += 1
        con.execute("""INSERT OR REPLACE INTO trophy_guess
                       (dex_key,guess,card_no,confidence,reason,url,local)
                       VALUES (?,?,?,?,?,?,?)""",
                    (key, design, no, conf, reason, url, local))
        con.commit()
    print(f"\n登録 {n}枚" + ("（--dry-run なので書いていない）" if a.dry_run else ""))
    print("このあと python build_dex.py で図鑑に反映する")


if __name__ == "__main__":
    main()
