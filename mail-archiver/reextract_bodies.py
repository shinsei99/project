#!/usr/bin/env python3
"""保存済みメールの本文を、原本(.eml)から作り直す（文字化けの修正用）。

ISO-2022-JP のデコード不良で本文にエスケープ列が残った 3,575通が対象（2026-08-27）。
原本は無傷なので、直したパーサ（imap_util._part_text）で再抽出して body_text と FTS を更新する。
本文が変わった行は embeddings を消す → embed_backfill.py で作り直す（化けたまま埋め込んでいたため）。

  /usr/bin/python3 reextract_bodies.py            # ESC が残る化け本文だけ直す
  /usr/bin/python3 reextract_bodies.py --all      # 全メールを再抽出（保険）
"""
from __future__ import annotations

import argparse
import os
import sys

import config
import db
import imap_util as iu


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="全メールを対象にする（既定は化けのみ）")
    args = ap.parse_args()

    conn = db.connect(config.DB_PATH)
    if args.all:
        rows = conn.execute("SELECT id, raw_path, subject, from_name, from_addr, "
                            "to_addrs, cc_addrs, body_text FROM messages").fetchall()
    else:
        rows = conn.execute(
            "SELECT id, raw_path, subject, from_name, from_addr, to_addrs, cc_addrs, body_text "
            "FROM messages WHERE body_text LIKE '%'||char(27)||'%'").fetchall()
    print("対象 {:,} 通".format(len(rows)), flush=True)

    fixed = missing = same = 0
    for i, r in enumerate(rows, 1):
        raw_abs = os.path.join(config.DATA_DIR, r["raw_path"])
        if not os.path.exists(raw_abs):
            missing += 1
            continue
        try:
            parsed = iu.parse_message(open(raw_abs, "rb").read())
        except Exception:
            missing += 1
            continue
        new_body = parsed["body_text"] or ""
        if new_body == (r["body_text"] or ""):
            same += 1
            continue
        addrs = " ".join(filter(None, [r["from_name"] or "", r["from_addr"] or "",
                                       r["to_addrs"] or "", r["cc_addrs"] or ""]))
        conn.execute("UPDATE messages SET body_text=? WHERE id=?", (new_body, r["id"]))
        conn.execute("DELETE FROM messages_fts WHERE rowid=?", (r["id"],))
        conn.execute("INSERT INTO messages_fts(rowid, subject, addrs, body) VALUES(?,?,?,?)",
                     (r["id"], r["subject"] or "", addrs, new_body))
        conn.execute("DELETE FROM embeddings WHERE message_id=?", (r["id"],))
        fixed += 1
        if i % 500 == 0:
            conn.commit()
            print("  {}/{} 直した {}".format(i, len(rows), fixed), flush=True)
    conn.commit()
    print("完了: 直した {:,} / 変化なし {:,} / 原本なし {:,}".format(fixed, same, missing),
          flush=True)
    print("→ 直した分の埋め込みは消したので embed_backfill.py で作り直す。", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
