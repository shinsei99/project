#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巡回写真の実体を Chatwork から取り直して data/web_images へ置く。

  chatwork_images には行があるのに、画像の実体（バイト）が手元に無いものがある。
  実体が無いと save_patrol_photos.py が物件フォルダへ入れられない。
  2026-09-05 に数えたら **84件のうち実体があるのは9件だけ**だった。

  ★なぜ実体が消えるのか
    data/web_images は「AIに見せるための一時置き場」で、古いものは掃除される。
    Chatwork 側にはファイルが残っているので、file_id から取り直せる。

  ★download_url の有効期限は30秒。取ったらその場で落とす（services/chatwork.py の注記）。

  使い方: fetch_patrol_photos.py            … 下見（何枚取れるか）
          fetch_patrol_photos.py --go       … 取り直す
          fetch_patrol_photos.py --go -n 20 … 20枚だけ
"""
import os, sys, json, time, sqlite3

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from services.chatwork import ChatworkClient, ChatworkError

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(BASE, "data", "app.db")
IMG = os.path.join(BASE, "data", "web_images")
GO = "--go" in sys.argv
LIMIT = None
for i, a in enumerate(sys.argv):
    if a == "-n" and i + 1 < len(sys.argv): LIMIT = int(sys.argv[i + 1])

os.makedirs(IMG, exist_ok=True)
con = sqlite3.connect(DB)

# 手元にある (room_id, file_id)
have = set()
for f in os.listdir(IMG):
    if not f.endswith(".json"): continue
    try:
        j = json.load(open(os.path.join(IMG, f)))
        have.add((int(j["room_id"]), int(j["file_id"])))
    except Exception:
        pass

rows = [(int(r[0]), int(r[1]), r[2] or "", r[3] or "", r[4] or "")
        for r in con.execute("""SELECT room_id, file_id, property_name, title, created_at
                                FROM chatwork_images ORDER BY created_at""")]
miss = [r for r in rows if (r[0], r[1]) not in have]

print("=" * 72)
print(("【実行】" if GO else "【下見】") + "  巡回写真の実体を取り直す")
print("=" * 72)
print(f"  DB {len(rows)}件 / 手元にある {len(rows)-len(miss)}件 / ★実体が無い {len(miss)}件")
if LIMIT: miss = miss[:LIMIT]
if not GO:
    print(f"\n  取り直す対象 {len(miss)}件")
    for r in miss[:12]:
        print(f"     {r[2] or '（物件名なし）':<20}{r[3][:30]:<32}{r[4][:16]}")
    if len(miss) > 12: print(f"     … 他 {len(miss)-12}件")
    print("\n  ※下見のみ。--go で取り直す")
    sys.exit(0)

cw = ChatworkClient()
ok = ng = 0
for n, (rid, fid, prop, title, created) in enumerate(miss, 1):
    try:
        blob, fn = cw.download_file(rid, fid)
    except ChatworkError as e:
        print(f"  ★取れない {prop} / {title[:24]} → {e}"); ng += 1; continue
    except Exception as e:
        print(f"  ★取れない {prop} / {title[:24]} → {type(e).__name__}: {e}"); ng += 1; continue
    if not blob:
        print(f"  ★中身が空 {prop} / {title[:24]}"); ng += 1; continue
    ext = os.path.splitext(fn or "")[1] or ".jpg"
    # ★同じ名前で上書きしない。room_id と file_id で一意にする
    name = f"cw_{rid}_{fid}{ext}"
    open(os.path.join(IMG, name), "wb").write(blob)
    json.dump({"room_id": rid, "file_id": fid, "filename": fn, "title": title,
               "property_name": prop, "created_at": created},
              open(os.path.join(IMG, name + ".json"), "w"), ensure_ascii=False)
    ok += 1
    if n % 10 == 0: print(f"  … {n}/{len(miss)}")
    time.sleep(0.35)          # ★Chatwork API は 5分300回。焦らない
print(f"\n  取れた {ok}枚 / 取れなかった {ng}枚")
print("  次は save_patrol_photos.py で物件フォルダへ入れる")
