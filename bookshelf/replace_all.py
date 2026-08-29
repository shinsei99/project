# -*- coding: utf-8 -*-
"""自炊本のテキスト層を作り直し、**原本の場所へ入れ替えて、題名に改名する**。

設計の要点:
- **二重に持たない。** 新ファイルを作って原本を消す、ではなく
  「一時ファイル → 検証 → 原本の場所へ os.replace（上書き）→ 題名へ改名」の順。
  途中で失敗しても原本には触れていない。
- **上書き前に必ず検証する**（ページ数・全ページの画像がバイト単位で同一・本文が入っている）。
  1つでも合わなければその本は飛ばし、原本をそのまま残す。
- 1冊終わるごとに入れ替えるので、途中で止めてもそこまでは反映済み。
"""
import hashlib, json, os, shutil, subprocess, sys, tempfile, time
import fitz

S = os.path.dirname(os.path.abspath(__file__))
DOCOCR = os.path.join(S, "dococr")
BOOKS = "/Users/apple/Library/CloudStorage/Dropbox-個人/書籍"
FONT = "japan"
LOG = os.path.join(S, "replace.log")


def log(msg):
    line = f"[{time.strftime('%H:%M:%S')}] {msg}"
    print(line, flush=True)
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def page_images(doc, tmp):
    """各ページの画像をファイルへ。1枚絵でなければ300dpiで描画する"""
    raw = {}
    for i in range(doc.page_count):
        imgs = doc[i].get_images(full=True)
        if len(imgs) == 1:
            px = doc.extract_image(imgs[0][0])
            if px["ext"] in ("jpeg", "jpg", "png"):
                open(os.path.join(tmp, f"{i:05d}.{px['ext']}"), "wb").write(px["image"])
                raw[i] = px["image"]
                continue
        doc[i].get_pixmap(dpi=300).save(os.path.join(tmp, f"{i:05d}.png"))
        raw[i] = None
    return raw


def run_ocr(tmp, jsonl):
    files = sorted(os.path.join(tmp, f) for f in os.listdir(tmp)
                   if f.rsplit(".", 1)[-1] in ("jpeg", "jpg", "png"))
    with open(jsonl, "w") as fh:
        for k in range(0, len(files), 40):
            subprocess.run([DOCOCR] + files[k:k + 40], stdout=fh, stderr=subprocess.DEVNULL)
    return len(files)


def build(src_path, tmp, jsonl, raw, out_path):
    src = fitz.open(src_path)
    by_page = {}
    for line in open(jsonl):
        o = json.loads(line)
        by_page[int(os.path.basename(o["file"]).split(".")[0])] = o
    out = fitz.open()
    st = {"lines": 0, "vert": 0, "chars": 0}
    for i in range(src.page_count):
        W, H = src[i].rect.width, src[i].rect.height
        page = out.new_page(width=W, height=H)
        if raw.get(i) is not None:
            page.insert_image(page.rect, stream=raw[i], keep_proportion=False)
        else:
            page.insert_image(page.rect, filename=os.path.join(tmp, f"{i:05d}.png"),
                              keep_proportion=False)
        o = by_page.get(i)
        if not o:
            continue
        for r in o["lines"]:
            t = r["t"].strip()
            if not t:
                continue
            bw, bh = max(r["w"] * W, 1.0), max(r["h"] * H, 1.0)
            x0, y_top = r["x"] * W, (1.0 - (r["y"] + r["h"])) * H
            vertical = bh > bw * 1.5
            span = bh if vertical else bw
            fs = max((bw if vertical else bh) * 0.95, 1.0)
            tl = fitz.get_text_length(t, fontname=FONT, fontsize=fs)
            if tl > 0:
                fs = max(min(fs * span / tl, span), 1.0)
            try:
                if vertical:
                    page.insert_text((x0 + bw * 0.85, y_top), t, fontname=FONT,
                                     fontsize=fs, rotate=270, render_mode=3)
                    st["vert"] += 1
                else:
                    page.insert_text((x0, y_top + bh * 0.82), t, fontname=FONT,
                                     fontsize=fs, render_mode=3)
                st["lines"] += 1
                st["chars"] += len(t)
            except Exception:
                pass
    out.save(out_path, garbage=4, deflate=True)
    src.close(); out.close()
    return st


def verify(orig_path, new_path):
    """入れ替えてよいか。**1つでも×なら原本に触らない**"""
    a = fitz.open(orig_path); b = fitz.open(new_path)
    try:
        if a.page_count != b.page_count:
            return False, f"ページ数が違う {a.page_count}≠{b.page_count}"
        chars = 0
        for i in range(a.page_count):
            ia, ib = a[i].get_images(full=True), b[i].get_images(full=True)
            if len(ia) == 1 and len(ib) == 1:
                ba = a.extract_image(ia[0][0])["image"]
                bb = b.extract_image(ib[0][0])["image"]
                if hashlib.sha256(ba).digest() != hashlib.sha256(bb).digest():
                    return False, f"{i+1}ページ目の画像が原本と違う"
            chars += len(b[i].get_text().strip())
        if chars < 50:
            return False, f"本文がほとんど入っていない（{chars}文字）"
        return True, f"{chars}文字"
    finally:
        a.close(); b.close()


def swap_and_rename(stem, title, new_path):
    """原本の場所へ上書きしてから題名へ改名する（二重に持たない・rmを使わない）"""
    orig = os.path.join(BOOKS, stem + ".pdf")
    final = os.path.join(BOOKS, title + ".pdf")
    os.replace(new_path, orig)        # 原本を新しい中身で置き換える
    os.replace(orig, final)           # 題名へ改名
    return final


def one(stem, title):
    orig = os.path.join(BOOKS, stem + ".pdf")
    final = os.path.join(BOOKS, title + ".pdf")
    if os.path.exists(final) and not os.path.exists(orig):
        log(f"済み: {title}")
        return "skip"
    if not os.path.exists(orig):
        log(f"★原本が無い: {stem}")
        return "missing"
    done = os.path.join(BOOKS, stem + "_OCR再構築.pdf")
    t0 = time.time()
    tmpdir = None
    try:
        if os.path.exists(done):
            cand = done                      # 8/29未明に作った分
            src_note = "作成済みを使う"
        else:
            doc = fitz.open(orig)
            n = doc.page_count
            tmpdir = tempfile.mkdtemp(prefix="ocr_")
            raw = page_images(doc, tmpdir)
            doc.close()
            jsonl = os.path.join(tmpdir, "ocr.jsonl")
            run_ocr(tmpdir, jsonl)
            cand = os.path.join(tmpdir, "out.pdf")
            build(orig, tmpdir, jsonl, raw, cand)
            src_note = f"{n}ページ"
        ok, why = verify(orig, cand)
        if not ok:
            log(f"★検証で不合格（原本はそのまま）: {stem} … {why}")
            return "bad"
        swap_and_rename(stem, title, cand)
        log(f"入替 {time.time()-t0:5.0f}秒  {src_note}  → 「{title}」（{why}）")
        return "ok"
    except Exception as e:
        log(f"★失敗（原本はそのまま）: {stem}: {type(e).__name__}: {str(e)[:80]}")
        return "err"
    finally:
        if tmpdir:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    pairs = []
    for line in open(os.path.join(S, "final_titles.tsv"), encoding="utf-8"):
        if "\t" in line:
            a, b = line.rstrip("\n").split("\t", 1)
            pairs.append((a, b))
    args = sys.argv[1:]
    if "--done-first" in args:
        pairs = [p for p in pairs
                 if os.path.exists(os.path.join(BOOKS, p[0] + "_OCR再構築.pdf"))]
    # まだ入れ替えていないものだけに絞る（途中で止めても続きから流せる）
    pairs = [p for p in pairs if os.path.exists(os.path.join(BOOKS, p[0] + ".pdf"))]
    if "--limit" in args:
        pairs = pairs[:int(args[args.index("--limit") + 1])]
    # 4並列で流すための取り分け（--shard 0/4 のように渡す）
    if "--shard" in args:
        i, n = (int(x) for x in args[args.index("--shard") + 1].split("/"))
        pairs = [p for k, p in enumerate(pairs) if k % n == i]
    res = {}
    for stem, title in pairs:
        r = one(stem, title)
        res[r] = res.get(r, 0) + 1
    log(f"— まとめ {res}")
