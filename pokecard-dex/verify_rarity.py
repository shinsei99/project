"""推定したレアリティ区間の「両端」だけAIで確認する。

infer_rarity.py は既知の印字から区間を埋めるが、区間の境目が本当に正しいかは
確認しないと分からない。そこで各区間の最小番号と最大番号のカードだけAIに読ませる。

  例) 101〜107 が AR と推定 → 101 と 107 を確認
      108〜120 が SR と推定 → 108 と 120 を確認

区間が正しければ両端の印字が推定値と一致する。ズレていれば境目が違うと分かり、
その区間だけ作り直せばよい。全枚数を読むより桁違いに安い。
"""
import json, os, re, shutil, sqlite3, subprocess, sys
from collections import defaultdict
from PIL import Image, ImageDraw, ImageFont

DEX = os.path.dirname(os.path.abspath(__file__))
CLAUDE = shutil.which("claude") or os.path.expanduser("~/.local/bin/claude")
PER_SHEET = 10

PROMPT = """画像 {fn} は、ポケモンカードの左下部分を{n}枚ぶん縦に並べたものです。
各行の左端に通し番号（1〜{n}）が振ってあります。

各行から「カード番号」と「レアリティ記号」を読み取ってください。
例: 「224/193 MA」なら no=224, total=193, rarity="MA"

重要: カード番号の**右側**にある記号だけがレアリティです。
番号の**左側**にある囲み文字（D E F G H I J など1文字）は
レギュレーションマークなので、レアリティとして扱わないでください。
番号の右に何も無い行は rarity を null にしてください。
イラストの上に文字が重なっている行もありますが、推測せず読めたものだけ答えてください。

JSONのみ出力。説明は不要。
{{"rows":[{{"i":1,"no":224,"total":193,"rarity":"MA"}}]}}"""


def make_sheet(cards, path):
    crops = []
    for f in cards:
        p = f if os.path.isabs(f) else os.path.join(DEX, f)
        im = Image.open(p).convert("RGB")
        w, h = im.size
        if h <= w:                      # 左右2枚組のカードは片方だけ使う
            im = im.crop((0, 0, w // 2, h)); w, h = im.size
        c = im.crop((int(w * 0.02), int(h * 0.86), int(w * 0.68), h))
        crops.append(c.resize((c.width * 3, c.height * 3), Image.LANCZOS))
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
        y += c.height + 14
    sheet.save(path, quality=92)


def ask(sheet, n, work):
    p = subprocess.run(
        [CLAUDE, "-p", PROMPT.format(fn=os.path.basename(sheet), n=n),
         "--tools", "Read", "--add-dir", work, "--model", "sonnet",
         "--output-format", "json"],
        capture_output=True, text=True, timeout=420, cwd=work)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[:200])
    m = re.search(r"\{.*\}", json.loads(p.stdout).get("result", ""), re.S)
    return {g["i"]: g for g in json.loads(m.group(0))["rows"]} if m else {}


def segments(con, sid):
    """(開始番号, 終了番号, レアリティ, 端のカード) の区間リストを作る。"""
    rows = con.execute("""SELECT local_id, rarity_inferred, local_file FROM cards
        WHERE set_id=? AND rarity_inferred IS NOT NULL AND local_file IS NOT NULL
          AND local_id NOT LIKE '%†%' ORDER BY CAST(local_id AS INTEGER)""", (sid,)).fetchall()
    segs = []
    for lid, rar, f in rows:
        if not str(lid).isdigit():
            continue
        n = int(lid)
        if segs and segs[-1][2] == rar and n == segs[-1][1] + 1:
            segs[-1][1] = n; segs[-1][4] = f
        else:
            segs.append([n, n, rar, f, f])
    return segs


def main():
    limit_sets = int(sys.argv[1]) if len(sys.argv) > 1 else 6
    con = sqlite3.connect(os.path.join(DEX, "data/cards.db"), timeout=240)
    con.execute("PRAGMA busy_timeout = 240000")

    targets = con.execute("""SELECT s.id, s.name FROM sets s
        WHERE EXISTS (SELECT 1 FROM cards c WHERE c.set_id=s.id AND c.rarity_inferred IS NOT NULL)
        ORDER BY s.release DESC LIMIT ?""", (limit_sets,)).fetchall()

    work = os.path.join(DEX, "data/_verify_tmp"); os.makedirs(work, exist_ok=True)
    checks, ok, ng = [], 0, 0
    for sid, nm in targets:
        for lo, hi, rar, f_lo, f_hi in segments(con, sid):
            checks.append((sid, nm, lo, rar, f_lo))
            if hi != lo:
                checks.append((sid, nm, hi, rar, f_hi))
    print(f"{len(targets)}セット / 確認する両端 {len(checks)}枚", flush=True)

    for b in range(0, len(checks), PER_SHEET):
        batch = checks[b:b + PER_SHEET]
        sheet = os.path.join(work, "v.jpg")
        try:
            make_sheet([c[4] for c in batch], sheet)
            got = ask(sheet, len(batch), work)
        except Exception as e:
            print(f"  読み取り失敗: {str(e)[:100]}", flush=True); continue
        for i, (sid, nm, n, rar, _) in enumerate(batch, 1):
            g = got.get(i) or {}
            read = (g.get("rarity") or "").upper()
            if not read:
                continue
            if read == rar.upper():
                ok += 1
            else:
                ng += 1
                print(f"  ⚠️ {nm[:16]:<18} {n:>4}番  推定 {rar} → 実際 {read}", flush=True)
    print(f"\n一致 {ok} / 不一致 {ng}", flush=True)
    if ok + ng:
        print(f"推定の正確さ {100*ok/(ok+ng):.0f}%", flush=True)


if __name__ == "__main__":
    main()
