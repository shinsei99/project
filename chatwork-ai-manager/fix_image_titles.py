#!/usr/bin/env python3
"""登録済み画像のタイトルを「投稿本文を正」として付け直す（2026-08-27・オーナー指示）。

**方針**（オーナーの言葉: 「きちんとチャットワークには写真と併せて物件名も入れて
投稿してるから、それをベースに認識してほしい」）:

  1. 画像と**同じメッセージ**の本文に管理物件マスターの正式名称があれば、それを正とする
     （vision がどう見えたかに関わらず上書きする）
  2. 本文に無ければ、**推測しない**。`物件名不明（要確認）` にする

なぜ2で推測しないのか（実データで確かめた事故）:
  2026-08-27 の巡回写真は 18:37/18:59/19:06/19:11 が「写真＋物件名」で投稿されている一方、
  **18:33・18:34 の2枚は本文が空**だった（18:27 の総括に4か所まとめて書いてある形）。
  この2枚に vision の推測でそれらしい名前が付いていたため、オーナーとの訂正のやり取りが
  最後まで噛み合わなかった。**間違った名前が自信ありげに付いている方が、
  「不明」と正直に出るより有害**、というのが今回の教訓。

  前後メッセージからの推定も試したが、同じルームの無関係な会話（ランドリー対応等）の
  物件名を拾って誤爆することが `_resolve_master_property_from_caption` の調査で
  確認済みなので採用しない。

使い方:
  python3 fix_image_titles.py --dry-run     # 何がどう変わるか見るだけ
  python3 fix_image_titles.py               # 実行
  python3 fix_image_titles.py --room-id 349546270
"""
from __future__ import annotations

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import execute, query  # noqa: E402
from services.attachments import _resolve_master_property_from_caption  # noqa: E402

UNKNOWN = "物件名不明（要確認）"
_TAG_RE = re.compile(r"\[/?(?:info|title|dtext:[^\]]*|download:\d+|preview[^\]]*|To:\d+|rp [^\]]*|qt|qtmeta[^\]]*)\]")
_FILE_RE = re.compile(r"\S+\.(?:jpe?g|png|gif|heic|webp)\s*\([^)]*\)", re.I)


def _caption_for(file_id) -> tuple[str | None, str | None]:
    """その画像を投稿したメッセージの本文（タグを外したもの）と message_id を返す。"""
    rows = query("SELECT message_id, body FROM messages WHERE body LIKE ? ORDER BY send_time LIMIT 1",
                 ("%[download:" + str(file_id) + "]%",))
    if not rows:
        rows = query("SELECT message_id, body FROM messages WHERE body LIKE ? ORDER BY send_time LIMIT 1",
                     ("%" + str(file_id) + "%",))
    if not rows:
        return None, None
    body = _TAG_RE.sub(" ", rows[0]["body"] or "")
    body = _FILE_RE.sub(" ", body)
    body = re.sub(r"claudeさん", " ", body)
    return re.sub(r"\s+", " ", body).strip() or None, rows[0]["message_id"]


def _all_master_names_in(text: str) -> set:
    """自由文に含まれる管理物件マスターの正式名称を**すべて**返す。

    `gis.match_property_in_text` は「一番具体的な1件」しか返さないので、
    1つのメッセージに4か所ぶん書かれている総括（例: 18:27「京橋センターパーク・
    エコパーキング京橋東・もと美モータープール・本庄西駐車場の巡回」）を
    「1件に決まった」と誤解してしまう。ここは全件見る。
    """
    import unicodedata
    t = unicodedata.normalize("NFKC", text or "")
    if not t:
        return set()
    out = set()
    for r in query("SELECT name FROM properties WHERE active=1"):
        n = r["name"]
        if n and unicodedata.normalize("NFKC", n) in t:
            out.add(n)
    return out


def _nearby_unique_master(room_id, file_id, window_sec=600):
    """本文が空の写真について、**前後10分の同じルームの会話**から物件名を拾う。

    ★1つに定まったときだけ採用する。2つ以上出てきたら「どれか分からない」ので
    採用しない（推測で名前を付けるのが今回の事故の元）。
    """
    rows = query("SELECT send_time FROM messages WHERE body LIKE ? LIMIT 1",
                 ("%[download:" + str(file_id) + "]%",))
    if not rows:
        return None, "投稿時刻が分からない"
    t0 = rows[0]["send_time"]
    near = query("SELECT body FROM messages WHERE room_id=? AND send_time BETWEEN ? AND ?",
                 (room_id, t0 - window_sec, t0 + window_sec))
    names = set()
    for r in near:
        names |= _all_master_names_in(_TAG_RE.sub(" ", r["body"] or ""))
    if len(names) == 1:
        return names.pop(), "前後10分の会話で1つに定まった"
    return None, ("前後の会話に%d件出てきて絞れない" % len(names) if names else "前後の会話にも物件名なし")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--room-id")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    sql = "SELECT room_id, file_id, title, property_name FROM chatwork_images"
    params = ()
    if args.room_id:
        sql += " WHERE room_id=?"
        params = (args.room_id,)
    rows = query(sql + " ORDER BY created_at", params)

    kept = fixed = unknown = nomsg = 0
    for r in rows:
        caption, _mid = _caption_for(r["file_id"])
        master = _resolve_master_property_from_caption(caption) if caption else None
        if master:
            new_title, new_prop, why = master, master, "本文に物件名あり"
        elif caption is None:
            nomsg += 1
            print("  投稿メッセージ不明 file_id=%s（現タイトル: %s）" % (r["file_id"], r["title"]))
            continue
        else:
            near, reason = _nearby_unique_master(r["room_id"], r["file_id"])
            if near:
                new_title, new_prop, why = near, near, "本文になし／" + reason
            else:
                new_title, new_prop, why = UNKNOWN, None, "本文になし／" + reason

        if (r["title"] or "") == new_title and (r["property_name"] or None) == new_prop:
            kept += 1
            continue
        print("  file_id=%s  %s" % (r["file_id"], why))
        print("      旧: title=%s / property=%s" % (r["title"], r["property_name"]))
        print("      新: title=%s / property=%s" % (new_title, new_prop))
        if not args.dry_run:
            execute("UPDATE chatwork_images SET title=?, property_name=? WHERE room_id=? AND file_id=?",
                    (new_title, new_prop, r["room_id"], r["file_id"]))
        if new_title == UNKNOWN:
            unknown += 1
        else:
            fixed += 1

    print("\n%s 検査 %d件 / 変更なし %d / 本文どおりに修正 %d / 不明に変更 %d / 投稿不明 %d"
          % ("[試算]" if args.dry_run else "[実行]", len(rows), kept, fixed, unknown, nomsg))
    if unknown:
        print("★『%s』になった写真は、オーナーに1枚ずつ見せて名前を聞くこと。" % UNKNOWN)


if __name__ == "__main__":
    main()
