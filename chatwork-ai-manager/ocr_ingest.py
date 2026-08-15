#!/usr/bin/env python3
"""スキャン画像PDFを claude vision で OCR して索引化する（バックグラウンド長時間ジョブ）。

- テキスト層のある PDF は mtime で即スキップ（既に text 取込済み）。
- テキスト層の無い（＝画像）PDF だけを OCR して取込む。
- 中断・再開可（OCR済みは content_hash/mtime で次回スキップ）。
- claude vision を1ファイル1回（先頭 max_pages ページ）呼ぶため時間がかかる。

使い方:
  python3 ocr_ingest.py                 # secrets の knowledge_source_dir 配下の PDF を OCR
  python3 ocr_ingest.py --dir "<folder>"
  python3 ocr_ingest.py --limit 20      # 先頭N件だけ（テスト）
  python3 ocr_ingest.py --max-pages 10
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.migrate import migrate  # noqa: E402
from services import config, knowledge  # noqa: E402
from services.settings import set_state  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--max-pages", type=int, default=15)
    args = ap.parse_args()
    migrate()

    root = args.dir or config.get("knowledge_source_dir")
    if not root or not os.path.isdir(root):
        print(f"フォルダにアクセスできません: {root}（ターミナルから/FDA必要）")
        sys.exit(1)

    pdfs = [p for p in knowledge.iter_supported(root) if p.lower().endswith(".pdf")]
    if args.limit:
        pdfs = pdfs[:args.limit]
    print(f"PDF {len(pdfs)} 件を確認（画像PDFのみOCR）", flush=True)

    ocr_ok, text_skip, empty, failed, chunks = 0, 0, 0, 0, 0
    for i, p in enumerate(pdfs, 1):
        rel = os.path.relpath(p, os.path.abspath(root))
        try:
            r = knowledge.ingest_file(p, category=knowledge.category_of(root, p), ocr_fallback=True)
            if r.get("unchanged"):
                text_skip += 1
            elif r.get("skipped"):
                empty += 1
                print(f"  [{i}/{len(pdfs)}] 画像認識なし: {rel}", flush=True)
            else:
                ocr_ok += 1
                chunks += r.get("chunks", 0)
                tag = "OCR" if str(r.get("mime", "")).endswith("-ocr") else "text"
                print(f"  [{i}/{len(pdfs)}] {tag} {r.get('chunks')}ch: {rel}", flush=True)
        except Exception as e:
            failed += 1
            print(f"  [{i}/{len(pdfs)}] FAIL {rel}: {type(e).__name__}: {e}", flush=True)
        if i % 25 == 0:
            set_state("ocr_progress", f"{i}/{len(pdfs)} (OCR {ocr_ok})")
    set_state("ocr_progress", f"完了 {len(pdfs)}件 (OCR {ocr_ok})")
    print(f"\n完了: OCR取込 {ocr_ok} / テキスト既取込スキップ {text_skip} / "
          f"認識なし {empty} / 失敗 {failed} / 追加チャンク {chunks}", flush=True)
    print(f"索引合計: {knowledge.stats()}", flush=True)


if __name__ == "__main__":
    main()
