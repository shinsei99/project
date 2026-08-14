"""カード画像の左下（番号＋レアリティの印字部）を並べた1枚を作り、AIにまとめて読ませる。

OCR（Apple Vision）はAR（全面イラスト）のカードで文字が絵に埋もれて読めなかった。
AIのビジョンなら背景と文字を区別できる。1回の呼び出しで複数枚まとめて読むことで
呼び出し回数を大幅に減らす。
"""
import json, os, re, shutil, sqlite3, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

DEX = "/Users/apple/pokecard-dex"
CLAUDE = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
PER_SHEET = 12          # 1回の呼び出しで読む枚数

PROMPT = """画像 {fn} は、ポケモンカードの左下部分を{n}枚ぶん縦に並べたものです。
各行の左端に通し番号（1〜{n}）が振ってあります。

各行から次の2つを読み取ってください。
・カード番号（例 224/193 の「224」と「193」）
・レアリティ（番号の右にある記号。C U R RR RRR AR SR SAR MA SA SSR UR MUR CHR CSR ACE K など）

重要: カード番号の**右側**の記号だけがレアリティです。番号の左の囲み文字
（D E F G H I J など1文字）はレギュレーションマークなので無視してください。
番号の右に何も無い行は rarity を null にしてください。
イラストの上に文字が乗っていて読みにくい行もありますが、推測せず読めたものだけ答えてください。

JSONのみを出力。説明は不要。
{{"rows":[{{"i":1,"no":224,"total":193,"rarity":"MA"}},{{"i":2,"no":18,"total":193,"rarity":"U"}}]}}"""


def make_sheet(cards, path):
    """[(id, local_file)] → 左下を縦に並べた1枚"""
    crops = []
    for cid, f in cards:
        p = f if os.path.isabs(f) else os.path.join(DEX, f)
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if h <= w:          # 「伝説の溶岩洞」等、左右2枚組のカードは横長で位置が違う
            im = im.crop((0, 0, w // 2, h)); w, h = im.size
        # 番号とレアリティは常に同じ位置（下端 90〜99%・左 3〜58%）に印字される。
        # 以前は 86% から切っていて番号が下端で切れ、読み取れなかった。
        c = im.crop((int(w * 0.03), int(h * 0.90), int(w * 0.58), int(h * 0.99)))
        c = c.resize((c.width * 4, c.height * 4), Image.LANCZOS)
        crops.append(c)
    W = max(c.width for c in crops) + 90
    H = sum(c.height + 14 for c in crops)
    sheet = Image.new("RGB", (W, H), (255, 255, 255))
    dr = ImageDraw.Draw(sheet)
    try:
        fo = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 30)
    except Exception:
        fo = ImageFont.load_default()
    y = 0
    for i, c in enumerate(crops, 1):
        dr.text((12, y + c.height // 2 - 16), str(i), fill=(0, 0, 0), font=fo)
        sheet.paste(c, (90, y))
        dr.line([(0, y + c.height + 7), (W, y + c.height + 7)], fill=(200, 200, 200), width=2)
        y += c.height + 14
    sheet.save(path, quality=92)


def ask(sheet_path, n, workdir):
    p = subprocess.run(
        [CLAUDE, "-p", PROMPT.format(fn=os.path.basename(sheet_path), n=n),
         "--tools", "Read", "--add-dir", workdir, "--model", "sonnet",
         "--output-format", "json"],
        capture_output=True, text=True, timeout=420, cwd=workdir)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:300])
    txt = json.loads(p.stdout).get("result", "")
    m = re.search(r"\{.*\}", txt, re.S)
    return json.loads(m.group(0))["rows"] if m else []


def setup(con):
    """AIが読んだレアリティを入れる列を用意する。TCGdex由来の rarity は壊さない。"""
    cols = {r[1] for r in con.execute("PRAGMA table_info(cards)")}
    if "rarity_ai" not in cols:
        con.execute("ALTER TABLE cards ADD COLUMN rarity_ai TEXT")
        con.execute("ALTER TABLE cards ADD COLUMN card_no TEXT")
        con.commit()


if __name__ == "__main__":
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 0     # 0 = 全部
    con = sqlite3.connect(os.path.join(DEX, "data/cards.db"), timeout=180)
    con.execute("PRAGMA busy_timeout = 180000")
    setup(con)

    # レアリティが無く、画像があり、まだAIに読ませていないカード
    # 対象は「同じセット内に印字ありカードが存在する」セットの空欄だけ。
    # スタートデッキ100 や DP期のように、そもそもカードにレアリティ記号が
    # 印字されていない商品を除外するための条件。
    # （発売日で絞る方法では MC が新しいために先頭に来てしまい機能しなかった）
    # 対象は「同じセット内に印字ありカードが存在する」セットの空欄だけ。
    # スタートデッキ100 や DP期のようにカードにレアリティ記号が無い商品を除外する。
    # 並び順は必ず発売日の新しい順。set_id 順にするとアルファベット順で
    # DP1 など印字が無い古いセットばかり処理してしまう（実際に0件で終わった）。
    # ⚠️ TCGdex の通し番号（local_id）と、カードに印字された番号は一致しない。
    # 実測: テラスタルフェスex の local_id=231 のカードは、実際には「171/187」と
    # 印字されていた。したがって local_id から「特別枠かどうか」は判定できない。
    #
    # そこで絞り込みをやめ、レアリティが未判明のカードは素直に全部読む。
    # 印字が無いカード（ハイクラスパックの通常枠）は空で返るだけで害はない。
    # 読み取った実際の番号は card_no に入るので、以後はそちらを基準にできる。
    sql = """SELECT c.id, c.local_id, c.name, c.local_file FROM cards c
             JOIN sets s ON c.set_id = s.id
             WHERE c.local_file IS NOT NULL
               AND c.rarity_ai IS NULL
               AND (c.rarity IS NULL OR c.rarity = 'None')
             ORDER BY s.release DESC, CAST(c.local_id AS INTEGER)"""
    todo = con.execute(sql + (f" LIMIT {limit}" if limit else "")).fetchall()
    print(f"対象 {len(todo):,}枚（レアリティが空・画像あり）", flush=True)
    if not todo:
        print("処理するものがありません。"); sys.exit()
    print(f"1回{PER_SHEET}枚まとめ読み → 呼び出し {len(todo)//PER_SHEET + 1}回", flush=True)

    work = os.path.abspath("data/_rarity_tmp"); os.makedirs(work, exist_ok=True)
    import time
    t0, filled, failed = time.time(), 0, 0
    for b in range(0, len(todo), PER_SHEET):
        batch = todo[b:b + PER_SHEET]
        sheet = os.path.join(work, "sheet.jpg")
        try:
            make_sheet([(r[0], r[3]) for r in batch], sheet)
            got = {g["i"]: g for g in ask(sheet, len(batch), work)}
        except Exception as e:
            failed += len(batch)
            print(f"\n  失敗: {str(e)[:120]}", flush=True)
            continue
        for i, r in enumerate(batch, 1):
            g = got.get(i) or {}
            rar, no, tot = g.get("rarity"), g.get("no"), g.get("total")
            con.execute("UPDATE cards SET rarity_ai=?, card_no=? WHERE id=?",
                        (rar or "", f"{no}/{tot}" if no and tot else None, r[0]))
            filled += bool(rar)
        con.commit()
        n = b + len(batch)
        el = time.time() - t0
        print(f"\r  {n:,}/{len(todo):,}  レアリティ判明 {filled:,}  失敗 {failed}  "
              f"{el/60:.0f}分経過 / 残り約{(len(todo)-n)/(n/el)/60:.0f}分", end="", flush=True)
    print(f"\n完了: {filled:,}枚にレアリティを設定 / 失敗 {failed}枚 / {(time.time()-t0)/60:.0f}分", flush=True)
