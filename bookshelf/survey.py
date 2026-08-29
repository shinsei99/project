# -*- coding: utf-8 -*-
"""書籍フォルダの棚卸し: ページ数・テキスト層の質・縦書きの有無を測る（OCRはしない）。"""
import fitz, glob, json, os, re, sys

os.chdir(sys.argv[1])
rows = []
for f in sorted(glob.glob("*.pdf")):
    if "_OCR" in f:
        continue
    try:
        d = fitz.open(f)
        n = d.page_count
        # 先頭・中間・末尾から最大24ページ標本を取る
        idx = sorted({int(n * k / 24) for k in range(24)} & set(range(n)))
        t = "".join(d[i].get_text() for i in idx)
        tt = re.sub(r"\s", "", t)
        hira = len(re.findall(r"[ぁ-ん]", tt)) / len(tt) if tt else 0.0
        # 画像ページか（テキストが極端に少ない＝未OCR）
        chars_per_page = len(tt) / max(len(idx), 1)
        rows.append({"f": f, "pages": n, "mb": round(os.path.getsize(f) / 1e6),
                     "hira": round(hira, 3), "cpp": round(chars_per_page)})
        d.close()
    except Exception as e:
        rows.append({"f": f, "err": str(e)[:60]})
    print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
