#!/usr/bin/env python3
"""ナレッジのノイズ（OCR文字化け・中身空の断片）を判定して無効化する。

安全設計:
  - 削除ではなく active=0 にするだけ（完全に復元可能）。
  - 無効化したものは meta='noise-cleanup' で印を付け、--undo で一括復元できる。
  - 「本文の日本語が極端に少ない かつ タイトルにも意味がない」ものだけを対象にする。
    → ファイル名に価値がある文書（平面図/請求書/写真 等）は温存する。

使い方:
  python3 cleanup_noise.py            # dry-run（対象を数えるだけ・既定）
  python3 cleanup_noise.py --apply    # 実際に無効化
  python3 cleanup_noise.py --undo     # 無効化したものを一括復元
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_conn, query  # noqa: E402
from db.migrate import migrate  # noqa: E402

_JP = re.compile(r"[぀-ヿ一-鿿]")
BODY_JP_MAX = 5     # 本文の日本語がこれ未満
BODY_LEN_MAX = 60   # かつ本文がこれ未満
TITLE_JP_MIN = 4    # タイトルの日本語がこれ以上なら「名前に価値あり」＝温存


def detect():
    docs = query(
        "SELECT d.id, d.title, d.category, "
        "COALESCE((SELECT GROUP_CONCAT(c.text,' ') FROM knowledge_chunks c WHERE c.doc_id=d.id),'') body "
        "FROM knowledge_documents d WHERE d.active=1"
    )
    garbage = []
    for d in docs:
        body = d["body"] or ""
        if len(_JP.findall(body)) < BODY_JP_MAX and len(body) < BODY_LEN_MAX \
                and len(_JP.findall(d["title"] or "")) < TITLE_JP_MIN:
            garbage.append(d)
    return garbage


def apply(rows):
    with get_conn() as conn:
        conn.executemany(
            "UPDATE knowledge_documents SET active=0, meta='noise-cleanup', updated_at=datetime('now','localtime') WHERE id=?",
            [(d["id"],) for d in rows],
        )


def undo():
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE knowledge_documents SET active=1, meta=NULL, updated_at=datetime('now','localtime') "
            "WHERE meta='noise-cleanup'"
        )
        return cur.rowcount


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--undo", action="store_true")
    args = ap.parse_args()
    migrate()

    if args.undo:
        n = undo()
        print(f"復元しました: {n} 件を有効化")
        return

    rows = detect()
    print(f"ノイズ判定: {len(rows)} 件（本文日本語<{BODY_JP_MAX}字・本文<{BODY_LEN_MAX}字・タイトル日本語<{TITLE_JP_MIN}字）")
    for d in rows[:15]:
        body = (d["body"] or "").strip().replace("\n", " ")
        print(f"  [{d['category']}] {d['title'][:26]} → 「{body[:24]}」")
    if len(rows) > 15:
        print(f"  …他 {len(rows) - 15} 件")

    if args.apply:
        apply(rows)
        remain = query("SELECT COUNT(*) n FROM knowledge_documents WHERE active=1")[0]["n"]
        print(f"\n無効化しました（復元可: python3 cleanup_noise.py --undo）。有効文書は {remain} 件になりました。")
    else:
        print("\n※ dry-run です。実行するには --apply、戻すには --undo。")


if __name__ == "__main__":
    main()
