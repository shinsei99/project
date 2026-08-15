"""
公式サイトのカード画像から「カード番号・総数・レアリティ」をAIに読ませる。

公式サイトはレアリティを公開していないが、**カード画像そのものには印字されている**
（画像左下に「068/076 U」の形）。ここを読めば2つの穴が同時に埋まる。

  1. マイカに出品が無く取れなかったカードのレアリティが判る
  2. 公式画像を正しい番号に紐づけられる。公式のファイル名は
     「050339_P_HERAKUROSU.jpg」のような通し番号で番号を含まないため、
     これまでカード名でしか照合できず、同名でレアリティ違いのカード
     （M6のギリーは 068番のU と 101番のSR がある）を取り違えていた

**構成は実測で決めたもの。変えると読めなくなる（再検証済み）:**

  ・切り出し   画像の下端（縦0.85〜1.0・横0.02〜0.66）を **4倍**に拡大
  ・並べ方     **10枚を縦一列**で1シート
  ・モデル     opus

  10枚シート（980x2660）は Claude 側で長辺1568pxに縮められても1枚あたり
  実効 577x144 が残り、10/10 正解した。これを詰めると破綻する:
    ・20枚を縦一列（4880px）… 縮小率が上がり上3枚が読めない
    ・24枚を3列×8段で2倍拡大 … 1枚 512x72 になり数字が潰れて読めない
    ・20枚を2列×10段で2.5倍   … 1枚 485x95 でやはり読めない
  1枚あたり実効の高さが140px前後を切ると読めなくなる、という線が実測の境界。

使い方:
    python read_official.py --check M6     # 正解が判るセットで精度を測る
    python read_official.py --missing      # レアリティが埋まっていない分だけ読む
    python read_official.py M6             # セットを指定して読む
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time

from PIL import Image, ImageDraw

DB = "data/cards.db"
PER_SHEET = 10           # 実測でこれ以上詰めると読めない
SCALE = 4                # 切り出しの拡大率
MODEL = "opus"           # 画像は sonnet だと固有名詞や数字を取り違える

PROMPT = (
    "Read sheet.png. ポケモンカード{n}枚の下部を縦に並べた画像です。"
    "各段の左に1〜{n}の番号があります。各段には「NNN/NNN レアリティ」の形で"
    "カード番号・総数・レアリティが印字されています（例: 009/076 RR）。"
    "レアリティは C U R RR RRR AR SR SAR SSR UR HR MA MUR FUR CHR CSR TR PR "
    "などの英字、または ● ◆ ★ の記号です。"
    "番号の左にある小さな四角（J や M6 の表記、レギュレーションマーク）は"
    "レアリティではありません。"
    "読めない場合、またはレアリティが印字されていない場合は null にしてください。"
    "推測はしないでください。JSONのみ出力: "
    '[{{"i":1,"no":"009","total":"076","rarity":"RR"}}]'
)


def setup(con):
    """official に読み取り結果の列を足す（既にあれば何もしない）。"""
    cols = {r[1] for r in con.execute("PRAGMA table_info(official)")}
    for name, typ in (("card_no", "INTEGER"), ("total_img", "INTEGER"),
                      ("rarity_img", "TEXT"), ("read_at", "REAL")):
        if name not in cols:
            con.execute(f"ALTER TABLE official ADD COLUMN {name} {typ}")
    con.commit()


def crop_bottom(path: str):
    """カード画像の下端（番号とレアリティが印字されている帯）を切り出す。

    横長の画像（左右に分かれたスタジアム等）は高さが縦長カードの半分ほどに
    なるため、切り出したあと高さを揃えてから並べる。
    """
    im = Image.open(path)
    w, h = im.size
    c = im.crop((int(w * 0.02), int(h * 0.85), int(w * 0.66), h))
    # 縦横比の違いを吸収して、1枚あたりの見た目の大きさを揃える
    target_h = 61
    if c.height != target_h:
        c = c.resize((int(c.width * target_h / c.height), target_h), Image.LANCZOS)
    return c.resize((c.width * SCALE, c.height * SCALE), Image.LANCZOS)


def make_sheet(paths, out: str):
    ims = [crop_bottom(p) for p in paths]
    W = max(i.width for i in ims)
    pad, lbl = 26, 60
    sheet = Image.new("RGB", (W + lbl, sum(i.height + pad for i in ims)), "white")
    d = ImageDraw.Draw(sheet)
    y = 0
    for n, im in enumerate(ims, 1):
        d.text((8, y + im.height // 2 - 5), str(n), fill="black")
        sheet.paste(im, (lbl, y))
        y += im.height + pad
    sheet.save(out)


def ask(work: str, n: int):
    """claude CLI に読ませて JSON を受け取る。"""
    try:
        r = subprocess.run(
            [shutil.which("claude") or "claude", "-p", PROMPT.format(n=n),
             "--model", MODEL, "--add-dir", work],
            cwd=work, capture_output=True, text=True, timeout=600,
            stdin=subprocess.DEVNULL)
    except subprocess.TimeoutExpired:
        return []
    out = r.stdout or ""
    m = re.search(r"\[[\s\S]*\]", out)
    if not m:
        return []
    try:
        return json.loads(m.group(0))
    except Exception:
        return []


def read_batch(rows):
    """rows は (card_id, local) の並び。戻り値は card_id → (no, total, rarity)。"""
    work = tempfile.mkdtemp(prefix="rar_")
    try:
        make_sheet([r[1] for r in rows], os.path.join(work, "sheet.png"))
        got = ask(work, len(rows))
        out = {}
        for item in got:
            i = item.get("i")
            if not isinstance(i, int) or not (1 <= i <= len(rows)):
                continue
            no = str(item.get("no") or "").strip()
            tot = str(item.get("total") or "").strip()
            rar = item.get("rarity")
            out[rows[i - 1][0]] = (
                int(no) if no.isdigit() else None,
                int(tot) if tot.isdigit() else None,
                (str(rar).strip() or None) if rar else None,
            )
        return out
    finally:
        shutil.rmtree(work, ignore_errors=True)


def targets(con, args):
    """読む対象を選ぶ。"""
    if "--missing" in args:
        # マイカでレアリティが判らなかったカードと同じセットの公式画像。
        #
        # ただし2007年より前のカードは、そもそも画像に「NNN/NNN レアリティ」が
        # 印字されていない（旧裏面とその復刻。20th Anniversary を700枚読ませて
        # 9枚しか判明しなかった）。読んでも無駄なので発売年で足切りする。
        return con.execute("""
            SELECT o.card_id, o.local FROM official o
            WHERE o.status='ok' AND o.local IS NOT NULL AND o.rarity_img IS NULL
              AND o.set_code IN (
                SELECT d.set_code FROM dex d JOIN dex_sets s ON s.set_code = d.set_code
                WHERE d.rarity IS NULL AND s.release >= '2007' GROUP BY d.set_code)
            ORDER BY o.set_code DESC, o.card_id""").fetchall()
    only = next((a for a in args if not a.startswith("--")), None)
    sql = ("SELECT card_id, local FROM official WHERE status='ok' AND local IS NOT NULL"
           + (" AND set_code = ?" if only else "")
           + " AND rarity_img IS NULL ORDER BY card_id")
    return con.execute(sql, (only,) if only else ()).fetchall()


def check(con, set_code: str, n=20):
    """マイカで正解が判っているセットで精度を測る。"""
    rows = con.execute("""SELECT card_id, local FROM official
                          WHERE set_code=? AND status='ok' AND local IS NOT NULL
                          ORDER BY card_id LIMIT ?""", (set_code, n)).fetchall()
    print(f"■ {set_code} の {len(rows)}枚で精度を測ります", flush=True)
    ok = ng = unk = 0
    for i in range(0, len(rows), PER_SHEET):
        got = read_batch(rows[i:i + PER_SHEET])
        for cid, (no, tot, rar) in got.items():
            truth = con.execute(
                "SELECT rarity, name FROM dex WHERE set_code=? AND card_no=?",
                (set_code, no)).fetchone() if no else None
            if not truth:
                unk += 1
                print(f"   {no}  AI:{rar}  → マイカに該当なし")
                continue
            good = truth[0] == rar
            ok += good
            ng += not good
            print(f"   {no:>3}/{tot}  AI:{str(rar):<5} 正解:{str(truth[0]):<5}"
                  f" {truth[1][:14]}  {'✓' if good else '✗'}")
    total = ok + ng
    print(f"\n正解 {ok}/{total}（{100*ok/max(1,total):.0f}%）"
          f"　照合できず {unk}件", flush=True)


def main():
    args = sys.argv[1:]
    con = sqlite3.connect(DB, timeout=300)
    con.execute("PRAGMA busy_timeout = 300000")
    setup(con)

    if "--check" in args:
        code = next((a for a in args if not a.startswith("--")), "M6")
        check(con, code)
        return

    rows = targets(con, args)
    sheets = (len(rows) + PER_SHEET - 1) // PER_SHEET
    print(f"対象 {len(rows):,}枚 / {sheets:,}シート"
          f"（1シート約40秒として約{sheets*40/3600:.1f}時間）", flush=True)
    if not rows:
        return

    t0, done, filled = time.time(), 0, 0
    for i in range(0, len(rows), PER_SHEET):
        batch = rows[i:i + PER_SHEET]
        got = read_batch(batch)
        data = [(no, tot, rar, time.time(), cid) for cid, (no, tot, rar) in got.items()]
        if data:
            for a in range(20):
                try:
                    con.executemany("""UPDATE official SET card_no=?, total_img=?,
                                       rarity_img=?, read_at=? WHERE card_id=?""", data)
                    con.commit()
                    break
                except sqlite3.OperationalError as e:
                    if "locked" not in str(e) or a == 19:
                        raise
                    time.sleep(3)
        done += len(batch)
        filled += sum(1 for _, _, r, _, _ in data if r)
        el = time.time() - t0
        print(f"\r  {done:,}/{len(rows):,}  レアリティ判明{filled:,}枚  "
              f"{el/60:.0f}分経過 / 残り約{(len(rows)-done)/(done/el)/60:.0f}分   ",
              end="", flush=True)

    print(f"\n完了: {done:,}枚読み取り / レアリティ判明 {filled:,}枚"
          f" / {(time.time()-t0)/60:.0f}分", flush=True)
    con.close()


if __name__ == "__main__":
    main()
