#!/usr/bin/env python3
"""既存の chatwork_images 行を、メッセージ本文優先のロジックで再判定・タイトル補正する
（TASK-20260827-009）。

背景: `services/attachments.py` の `read_chatwork_image` はキャッシュ済みの画像を
二度と解析し直さない（vision呼び出しは定額枠を消費するため）。よってロジックを直しただけでは
**既に登録済みの画像のタイトルは直らない**。ここでは vision を呼び直さず、
`chatwork_images` の各行について投稿メッセージ本文（**画像と同一メッセージのキャプションのみ**。
前後メッセージは対象外＝理由は `_resolve_master_property_from_caption` 参照）を
`_resolve_master_property_from_caption` で再チェックし、管理物件マスターの正式名称が
キャプションに明記されていれば title/property_name をそれで上書きする（安価・決定的・
何度でも安全に再実行できる=冪等）。キャプションが無い画像は対象外（現状維持）。

`chatwork_images` に message_id は保存されていない（file_idのみ）ため、
`messages.body LIKE '%[download:<file_id>]%'` で該当room内から投稿メッセージを逆引きする。

使い方:
  python3 retitle_images.py                 # 全件を対象に再判定（変更があった行だけ更新）
  python3 retitle_images.py --room-id 349546270
  python3 retitle_images.py --dry-run        # 更新はせず変更予定だけ表示
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import execute, query  # noqa: E402
from services.attachments import _anchor_caption, _resolve_master_property_from_caption  # noqa: E402


def _find_message_id(room_id, file_id):
    rows = query(
        "SELECT message_id FROM messages WHERE room_id=? AND body LIKE ?",
        (room_id, f"%[download:{file_id}]%"),
    )
    return rows[0]["message_id"] if rows else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room-id", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sql = "SELECT room_id, file_id, filename, title, property_name FROM chatwork_images WHERE 1=1"
    params = []
    if args.room_id:
        sql += " AND room_id=?"
        params.append(args.room_id)
    rows = query(sql, tuple(params))

    checked = 0
    no_message = 0
    unchanged = 0
    updated = 0
    for r in rows:
        checked += 1
        message_id = _find_message_id(r["room_id"], r["file_id"])
        if not message_id:
            no_message += 1
            continue
        caption = _anchor_caption(r["room_id"], message_id)
        forced = _resolve_master_property_from_caption(caption)
        if not forced:
            unchanged += 1
            continue
        if forced == r["title"] and forced == r["property_name"]:
            unchanged += 1
            continue
        print(f"room={r['room_id']} file={r['file_id']} filename={r['filename']!r} "
              f"title: {r['title']!r} -> {forced!r} / property_name: {r['property_name']!r} -> {forced!r}")
        updated += 1
        if not args.dry_run:
            execute(
                "UPDATE chatwork_images SET title=?, property_name=? WHERE room_id=? AND file_id=?",
                (forced, forced, r["room_id"], r["file_id"]),
            )

    print(f"\n検査 {checked} 件 / 投稿メッセージ不明 {no_message} 件 / "
          f"変更なし {unchanged} 件 / {'更新予定' if args.dry_run else '更新'} {updated} 件")


if __name__ == "__main__":
    main()
