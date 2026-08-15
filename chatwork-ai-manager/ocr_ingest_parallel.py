#!/usr/bin/env python3
"""スキャン画像PDFを claude vision で OCR 取込（並列版・夜間バッチ用）。

ocr_ingest.py の並列版。テキスト層PDFは mtime で即スキップ、画像PDFのみOCR。
中断・再開可（OCR済みは content_hash/mtime で次回スキップ）。
SQLiteはWAL＋busy_timeoutで並列書込に対応。

使い方:
  python3 ocr_ingest_parallel.py                 # secretsの取込元・既定6並列
  python3 ocr_ingest_parallel.py --workers 8
  python3 ocr_ingest_parallel.py --dir "<folder>" --limit 50
"""
import argparse
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.migrate import migrate  # noqa: E402
from services import config, knowledge  # noqa: E402
from services.settings import set_state  # noqa: E402

_lock = threading.Lock()
_counts = {"ocr": 0, "text": 0, "empty": 0, "failed": 0, "chunks": 0, "done": 0}


def _process(path, root):
    rel = os.path.relpath(path, os.path.abspath(root))
    try:
        r = knowledge.ingest_file(path, category=knowledge.category_of(root, path), ocr_fallback=True)
        with _lock:
            _counts["done"] += 1
            if r.get("unchanged"):
                _counts["text"] += 1
                tag = "skip(変更なし)"
            elif r.get("skipped"):
                _counts["empty"] += 1
                tag = "認識なし"
            elif r.get("used_ocr"):
                _counts["ocr"] += 1
                _counts["chunks"] += r.get("chunks", 0)
                tag = f"OCR {r.get('chunks')}ch"
            else:
                _counts["text"] += 1
                _counts["chunks"] += r.get("chunks", 0)
                tag = f"text {r.get('chunks')}ch"
        return f"OK [{tag}] {rel}"
    except Exception as e:
        with _lock:
            _counts["done"] += 1
            _counts["failed"] += 1
        return f"FAIL {rel}: {type(e).__name__}: {e}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()
    migrate()

    root = args.dir or config.get("knowledge_source_dir")
    if not root or not os.path.isdir(root):
        print(f"フォルダにアクセスできません: {root}（ターミナル/FDA必要）")
        sys.exit(1)

    pdfs = [p for p in knowledge.iter_supported(root) if p.lower().endswith(".pdf")]
    if args.limit:
        pdfs = pdfs[:args.limit]
    total = len(pdfs)
    print(f"PDF {total} 件を {args.workers} 並列でOCR確認（画像PDFのみOCR）", flush=True)
    set_state("ocr_progress", f"0/{total} (parallel x{args.workers})")

    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(_process, p, root): p for p in pdfs}
        for i, fut in enumerate(as_completed(futs), 1):
            msg = fut.result()
            if i % 10 == 0 or "FAIL" in msg or "OCR" in msg:
                print(f"[{i}/{total}] {msg}", flush=True)
            if i % 25 == 0:
                set_state("ocr_progress",
                          f"{i}/{total} (OCR {_counts['ocr']} / fail {_counts['failed']})")

    set_state("ocr_progress", f"完了 {total}件 (OCR {_counts['ocr']})")
    print(f"\n完了: OCR取込 {_counts['ocr']} / テキスト既取込 {_counts['text']} / "
          f"認識なし {_counts['empty']} / 失敗 {_counts['failed']} / 追加チャンク {_counts['chunks']}",
          flush=True)
    print(f"索引合計: {knowledge.stats()}", flush=True)


if __name__ == "__main__":
    main()
