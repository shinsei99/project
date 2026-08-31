#!/usr/bin/env python3
"""添付ファイルの**中身**を取り出して全文検索に載せる（2026-08-31 追加）。

    /usr/bin/python3 attach_extract.py --stats            進み具合だけ見る
    /usr/bin/python3 attach_extract.py --max-minutes 45   夜間用（時間で切る）
    /usr/bin/python3 attach_extract.py --no-ocr           テキスト層のあるものだけ
    /usr/bin/python3 attach_extract.py --retry-empty      「文字なし」をもう一度だけ試す

## なぜ要るか

これまで添付は「保管してダウンロードできる」だけで、**中身は検索できなかった**。
2026-08-31 に実際に困った例: PTA大会の会場「スイスホテル南海大阪」は
**メール本文に一度も出てこず**、スキャンPDFの中にしかない。どんな語で検索しても当たらなかった。

添付は 39,726件（PDF 26,669 / doc 4,052 / xls 1,681 / xlsx 1,573 / docx 1,112 / 画像 3,700ほか）。
PDFを60件抜き取って調べたところ **58%はテキスト層あり・42%はスキャン画像**だった。

## 2段構え

1. **テキスト層・Office** … その場で取り出す（速い）
2. **スキャン画像** … macOS Vision で OCR（`tools/ocr_pdf`）

★OCRに claude vision を使わない理由: AI業務マネージャーの夜間OCRと**同じ定額枠を取り合う**うえ、
  実測 186件/2時間＝スキャン11,100件で約60晩かかる。macOS Vision は OS 同梱で無料・
  ネットワーク不要・**実測 2.3秒/ページ**。並列も効く。

## 中断と再開

**1添付1行**を `attachment_texts` に必ず書く（文字が取れなくても `method='none'` で記録）。
書かないと毎晩同じファイルを試して前に進まない（`ocr_ingest.py` の教訓）。

★`--limit` と `--max-new` は別物。`--limit` は対象リストの先頭N件を切り出すだけなので、
  毎晩流すと同じ先頭を舐めて終わる。夜間は `--max-minutes` / `--max-new` を使うこと。

## 実行するPython

`/usr/bin/python3`（pdfplumber / openpyxl / python-docx / xlrd が入っている）。
`.venv` には入っていないので、**夜間ジョブからも /usr/bin/python3 で呼ぶ**
（`translate_english.py` と同じ流儀）。ライブラリが無い形式は黙って飛ばさず「未対応」と記録する。
"""
from __future__ import annotations

import argparse
import concurrent.futures as futures
import os
import re
import subprocess
import sys
import time
from typing import Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config  # noqa: E402
import db  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
OCR_BIN = os.path.join(HERE, "tools", "ocr_pdf")

# 1添付あたりの上限。索引DBが際限なく膨らむのを防ぐ（1.6GB→どこまで増えるかを測れるように）
MAX_CHARS = 200_000
# これ未満ならテキスト層が無いとみなす（表紙だけ文字があるPDFを拾わないため）
MIN_TEXT_CHARS = 30
OCR_MAX_PAGES = 20
OCR_TIMEOUT = 240

TEXT_EXTS = [".pdf", ".docx", ".xlsx", ".xlsm", ".xls", ".doc",
             ".csv", ".txt", ".md", ".html", ".htm"]
IMAGE_EXTS = [".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff"]


def _clean(s: str) -> str:
    """空白と改行を詰める。trigram索引に無駄な空白を入れない。"""
    s = re.sub(r"[ \t　]+", " ", s or "")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()[:MAX_CHARS]


# ---------------------------------------------------------------- 取り出し

def _read_text_file(path: str) -> str:
    raw = open(path, "rb").read()
    for enc in ("utf-8", "cp932", "euc-jp"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def _extract_pdf(path: str) -> Tuple[str, Optional[int]]:
    import pdfplumber
    import warnings
    warnings.filterwarnings("ignore")
    with pdfplumber.open(path) as pdf:
        pages = pdf.pages[:OCR_MAX_PAGES]
        return "\n".join((p.extract_text() or "") for p in pages), len(pdf.pages)


def _extract_docx(path: str) -> Tuple[str, Optional[int]]:
    import docx
    d = docx.Document(path)
    parts = [p.text for p in d.paragraphs]
    for t in d.tables:                       # 表の中に本文があることが多い（案内状・様式）
        for row in t.rows:
            parts.append("\t".join(c.text for c in row.cells))
    return "\n".join(parts), None


def _extract_xlsx(path: str) -> Tuple[str, Optional[int]]:
    import openpyxl
    try:
        wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    except Exception:
        # ★openpyxl は一部の .xlsx で「could not read stylesheet」で開けない
        #   （実データ約6,000件のうち20件＝0.3%。書式が壊れているだけで中身は読める）。
        #   .xlsx は zip なので、中の XML から文字だけ拾って検索には載せる。
        return _extract_xlsx_raw(path), None
    parts = []
    for ws in wb.worksheets:
        parts.append("# " + str(ws.title))
        for row in ws.iter_rows(values_only=True):
            vals = [str(v) for v in row if v is not None]
            if vals:
                parts.append("\t".join(vals))
    wb.close()
    return "\n".join(parts), None


def _extract_xlsx_raw(path: str) -> str:
    """壊れた .xlsx から、zip の中のXMLを直接読んで文字だけ拾う（予備の手）。"""
    import zipfile
    import xml.etree.ElementTree as ET
    out = []
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist()
                 if n == "xl/sharedStrings.xml" or n.startswith("xl/worksheets/sheet")]
        for n in names:
            try:
                root = ET.fromstring(z.read(n))
            except ET.ParseError:
                continue
            for el in root.iter():
                # <t>（共有文字列）と <v>（値）に中身が入っている
                if el.tag.rsplit("}", 1)[-1] in ("t", "v") and (el.text or "").strip():
                    out.append(el.text.strip())
    return "\n".join(out)


def _extract_xls(path: str) -> Tuple[str, Optional[int]]:
    # ★xlrd 2.x は .xlsx を捨てて .xls 専用になった（新しい方は openpyxl が見る）
    import xlrd
    book = xlrd.open_workbook(path)
    parts = []
    for sh in book.sheets():
        parts.append("# " + sh.name)
        for r in range(sh.nrows):
            vals = [str(v) for v in sh.row_values(r) if str(v).strip()]
            if vals:
                parts.append("\t".join(vals))
    return "\n".join(parts), None


def _extract_doc(path: str) -> Tuple[str, Optional[int]]:
    """旧Word。macOS 同梱の textutil で取り出す（antiword は入っていない）。"""
    r = subprocess.run(["textutil", "-convert", "txt", "-stdout", path],
                       capture_output=True, timeout=120)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace")[:200])
    raw = r.stdout
    for enc in ("utf-8", "cp932"):           # textutil は Shift_JIS のまま返すことがある
        try:
            return raw.decode(enc), None
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace"), None


def _extract_html(path: str) -> Tuple[str, Optional[int]]:
    s = _read_text_file(path)
    s = re.sub(r"(?is)<(script|style).*?</\1>", " ", s)
    s = re.sub(r"(?s)<[^>]+>", " ", s)
    return s, None


_EXTRACTORS = {
    ".pdf": _extract_pdf, ".docx": _extract_docx,
    ".xlsx": _extract_xlsx, ".xlsm": _extract_xlsx,
    ".xls": _extract_xls, ".doc": _extract_doc,
    ".html": _extract_html, ".htm": _extract_html,
    ".csv": lambda p: (_read_text_file(p), None),
    ".txt": lambda p: (_read_text_file(p), None),
    ".md": lambda p: (_read_text_file(p), None),
}


def ocr(path: str) -> str:
    """macOS Vision で文字起こし。土台が無ければ RuntimeError（黙って空にしない）。"""
    if not os.path.exists(OCR_BIN):
        raise RuntimeError("OCRの土台が無い: {}（tools/build.sh で作る）".format(OCR_BIN))
    r = subprocess.run([OCR_BIN, path, "--max-pages", str(OCR_MAX_PAGES)],
                       capture_output=True, timeout=OCR_TIMEOUT)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or b"").decode("utf-8", "replace")[:200])
    return r.stdout.decode("utf-8", "replace").replace("\x0c", "\n")


def extract_one(path: str, filename: str, use_ocr: bool) -> Tuple[str, str, Optional[int], str]:
    """1件ぶん。戻り値 (method, text, pages, error)。**例外は投げない**。"""
    ext = os.path.splitext(filename)[1].lower()
    if not os.path.exists(path):
        return "error", "", None, "実体が無い"
    try:
        if ext in IMAGE_EXTS:
            if not use_ocr:
                return "skip", "", None, ""
            t = _clean(ocr(path))
            return ("ocr" if len(t) >= MIN_TEXT_CHARS else "none"), t, None, ""

        fn = _EXTRACTORS.get(ext)
        if fn is None:
            return "error", "", None, "未対応の形式: {}".format(ext)

        try:
            raw, pages = fn(path)
        except ImportError as e:              # ライブラリ不足を「文字なし」と混同しない
            return "error", "", None, "ライブラリ不足: {}".format(e)
        text = _clean(raw)

        if ext == ".pdf" and len(text) < MIN_TEXT_CHARS:
            # テキスト層が無い＝スキャン画像。OCRへ回す
            if not use_ocr:
                return "skip", "", pages, ""
            t = _clean(ocr(path))
            return ("ocr" if len(t) >= MIN_TEXT_CHARS else "none"), t, pages, ""

        return ("text" if len(text) >= MIN_TEXT_CHARS else "none"), text, pages, ""
    except subprocess.TimeoutExpired:
        return "error", "", None, "時間切れ"
    except Exception as e:                     # noqa: BLE001 … 1件で全体を止めない
        return "error", "", None, "{}: {}".format(type(e).__name__, str(e)[:150])


# ---------------------------------------------------------------- 本体

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-minutes", type=float, default=0, help="この分数で切り上げる（夜間用）")
    ap.add_argument("--max-new", type=int, default=0, help="処理できた件数がNに達したら終了")
    ap.add_argument("--limit", type=int, default=0, help="対象の先頭N件だけ（テスト用）")
    ap.add_argument("--since-days", type=int, default=0,
                    help="この日数より新しいメールの添付だけ（新着を先に片付ける用）")
    ap.add_argument("--workers", type=int, default=4, help="同時に処理する数")
    ap.add_argument("--no-ocr", action="store_true", help="OCRしない（テキスト層のみ）")
    ap.add_argument("--ocr-only", action="store_true", help="OCRが要るものだけ")
    ap.add_argument("--retry-empty", action="store_true", help="none/error をもう一度試す")
    ap.add_argument("--stats", action="store_true", help="進み具合だけ出して終わる")
    args = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    db.init_schema(conn)                       # 新しい表は CREATE IF NOT EXISTS で足りる

    if args.stats:
        s = db.attachment_text_stats(conn)
        print("添付 {:,}件 / 処理済み {:,}件".format(s["添付総数"], s["処理済み"]))
        for k, v in sorted(s["内訳"].items()):
            print("  {:6s} {:>7,}件  {:>12,}文字".format(k, v["件"], v["文字"]))
        return 0

    exts = (IMAGE_EXTS if args.ocr_only else TEXT_EXTS + IMAGE_EXTS)
    todo = db.pending_attachments(conn, exts, limit=args.limit,
                                  retry_empty=args.retry_empty,
                                  since_days=args.since_days)
    use_ocr = not args.no_ocr
    started = time.time()
    print("{} 添付の中身を索引に入れる … 対象 {:,}件{} / OCR {} / 同時 {}".format(
        time.strftime("%Y-%m-%d %H:%M:%S"), len(todo),
        "（直近{}日ぶん）".format(args.since_days) if args.since_days else "",
        "する" if use_ocr else "しない", args.workers), flush=True)

    counts = {"text": 0, "ocr": 0, "none": 0, "error": 0, "skip": 0}
    done = 0
    stop_reason = "対象をすべて処理した"

    def work(row):
        path = os.path.join(config.DATA_DIR, row["path"])
        return row, extract_one(path, row["filename"], use_ocr)

    with futures.ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        it = iter(todo)
        pending = set()
        # ★全部を一度に投げない。--max-minutes で切るとき、投げた分だけ無駄に走るため
        for _ in range(args.workers * 2):
            nxt = next(it, None)
            if nxt is None:
                break
            pending.add(pool.submit(work, nxt))

        while pending:
            finished, pending = futures.wait(pending, return_when=futures.FIRST_COMPLETED)
            for f in finished:
                row, (method, text, pages, err) = f.result()
                if method != "skip":
                    db.save_attachment_text(conn, row["id"], row["message_id"],
                                            method, text, pages, err)
                    if counts.get(method) is not None:
                        done += 1
                counts[method] = counts.get(method, 0) + 1
                if done % 50 == 0:
                    conn.commit()
                    print("  {:,}件 … text {:,} / ocr {:,} / 文字なし {:,} / 失敗 {:,}".format(
                        done, counts["text"], counts["ocr"], counts["none"],
                        counts["error"]), flush=True)

            over_time = args.max_minutes and (time.time() - started) / 60 >= args.max_minutes
            over_new = args.max_new and done >= args.max_new
            if over_time or over_new:
                stop_reason = "時間切れ（{}分）".format(args.max_minutes) if over_time \
                    else "上限（{}件）に達した".format(args.max_new)
                for f in pending:
                    f.cancel()
                break
            for _ in range(len(finished)):
                nxt = next(it, None)
                if nxt is None:
                    break
                pending.add(pool.submit(work, nxt))

    conn.commit()
    mins = (time.time() - started) / 60
    print("{} 終了 {:.1f}分 / {}".format(time.strftime("%Y-%m-%d %H:%M:%S"), mins, stop_reason))
    print("  テキスト層 {:,} / OCR {:,} / 文字なし {:,} / 失敗 {:,} / 見送り {:,}".format(
        counts["text"], counts["ocr"], counts["none"], counts["error"], counts["skip"]))
    s = db.attachment_text_stats(conn)
    print("  進み具合: {:,} / {:,}件（{:.1f}%）".format(
        s["処理済み"], s["添付総数"], 100.0 * s["処理済み"] / max(1, s["添付総数"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
