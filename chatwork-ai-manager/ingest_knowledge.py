#!/usr/bin/env python3
"""社内ナレッジ取込 CLI（Dropbox 共有フォルダ等を走査して索引化）。

⚠ CloudStorage(Dropbox/GDrive) は launchd 常時起動プロセスからは TCC で読めない。
   → この取込は「ターミナルから手動実行」すること（Terminal の権限を継承して読める）。
   取込後の Q&A 検索はローカル SQLite だけを読むので常時起動でも動く。

使い方:
  python3 ingest_knowledge.py --dir "<フォルダ>"            # 走査して取込
  python3 ingest_knowledge.py --dir "<フォルダ>" --dry-run   # 対象ファイルの一覧だけ
  python3 ingest_knowledge.py --dir "<フォルダ>" --limit 30  # 先頭N件だけ（テスト）
  python3 ingest_knowledge.py --file "<単一ファイル>"        # 1ファイルだけ
未指定なら secrets.toml の knowledge_source_dir を使う。
category は共有フォルダ直下のサブフォルダ名（営業・募集 等）を自動採用。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.migrate import migrate  # noqa: E402
from services import config, knowledge  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--file")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--full", action="store_true", help="変更なしでも全ファイル再取込")
    ap.add_argument("--company",
                    help="この資料がどの会社のものか（会社の壁）。省略すると大京商事株式会社。\n"
                         "★別会社のフォルダを取り込むときは必ず指定する。忘れると全体チャットから読めてしまう。")
    args = ap.parse_args()
    migrate()

    if args.file:
        res = knowledge.ingest_file(args.file, force=args.full, company=args.company)
        print(f"{os.path.basename(args.file)} -> {res}")
        return

    root = args.dir or config.get("knowledge_source_dir")
    if not root:
        print("取込元フォルダが未指定です（--dir または secrets.toml の knowledge_source_dir）。")
        sys.exit(1)
    if not os.path.isdir(root):
        print(f"フォルダにアクセスできません: {root}\n"
              "（CloudStorage はターミナルから実行してください。TCC 権限が必要です）")
        sys.exit(1)

    if args.dry_run:
        files = knowledge.iter_supported(root, limit=args.limit)
        print(f"対象 {len(files)} 件（root={os.path.abspath(root)}／会社={args.company or '大京商事株式会社(既定)'}）")
        for p in files:
            print(f"  [{knowledge.category_of(root, p)}] {os.path.relpath(p, os.path.abspath(root))}")
        return

    def _progress(i, total, path):
        print(f"  [{i}/{total}] {os.path.relpath(path, os.path.abspath(root))}", flush=True)

    res = knowledge.ingest_folder(root, incremental=not args.full, limit=args.limit,
                                  progress=_progress, company=args.company)
    st = knowledge.stats()
    print(f"\n完了: 取込 {res['ingested']} / 変更なし {res['unchanged']} / "
          f"スキップ {res['skipped']} / 失敗 {res['failed']} / 無効化 {res['pruned']} / "
          f"追加チャンク {res['chunks']}")
    if res["errors"]:
        print("失敗ファイル:")
        for e in res["errors"][:20]:
            print(f"  - {e}")
    print(f"索引合計: 有効文書 {st['documents']} 件 / チャンク {st['chunks']} 件")


if __name__ == "__main__":
    main()
