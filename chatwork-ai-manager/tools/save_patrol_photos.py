#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""巡回写真を、Dropboxの物件フォルダ「記録・写真/巡回/」へ保存する。

  data/web_images に実体がある画像を、chatwork_images の property_name で
  物件フォルダへ振り分ける。ファイル名は「YYYY-MM-DD_タイトル.拡張子」。
  AIの説明文は .txt にしない（chatwork_images.description に残っているのでそちらを引く）。

  使い方:  save_patrol_photos.py          … 下見
           save_patrol_photos.py --go     … 実行

  ★大京商事の物件だけを対象にする（新誠プロパティの物件は保存先が別）。
  ★同じ file_id を二度保存しない（記録用テーブルで管理）。
"""
import os, re, sys, json, shutil, sqlite3, unicodedata, datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB   = os.path.join(BASE, "data", "app.db")
IMG  = os.path.join(BASE, "data", "web_images")
MP   = "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/物件・管理/管理物件"
GO   = "--go" in sys.argv
N = lambda s: unicodedata.normalize("NFC", s)

def norm(s):
    s = unicodedata.normalize("NFKC", str(s)).lower()
    return re.sub(r"[\s　・･,，.。\-ー－_/\\'\"()（）\[\]【】]", "", s)

# ---------- 物件フォルダの索引（サブ物件も含める） ----------
folders = {}
for kind in sorted(os.listdir(MP)):
    kp = os.path.join(MP, kind)
    # ★「_旧管理物件」には巡回写真を入れない（2026-09-05）
    if not os.path.isdir(kp) or kind.startswith("_"): continue
    for prop in sorted(os.listdir(kp)):
        pp = os.path.join(kp, prop)
        if not os.path.isdir(pp): continue
        folders[norm(prop)] = pp
        # サブ物件（例: 隆生福祉会（ゆめ）/ゆめあまみ）も引けるようにする
        for sub in sorted(os.listdir(pp)):
            sp = os.path.join(pp, sub)
            if os.path.isdir(sp) and not sub.startswith("."):
                folders.setdefault(norm(sub), sp)

# ★社内では物件を正式名称で呼ばない。properties.aliases に登録した呼び名も引けるようにする。
#   これが無いと「ユーリムズビル」の巡回写真が11枚まるごと保存できなかった（2026-09-05）。
_c1 = sqlite3.connect(DB)
ALIAS = {}                      # 呼び名 → 正式名称
GROUP = {}                      # 正式名称 → その物件の呼び名すべて（正式名も含む）
for (nm, al) in _c1.execute("SELECT name, aliases FROM properties WHERE active=1"):
    g = [nm] + [a.strip() for a in re.split(r"[\n,、]", al or "") if a.strip()]
    GROUP[nm] = g
    for a in g: ALIAS.setdefault(norm(a), nm)
_c1.close()

# ★正式名称とフォルダ名が違う物件がある（例 マスタ「MDXビル」／フォルダ「MDXBLDG」）。
#   正式名だけで引くと外れるので、**その物件の呼び名を順に当てて**フォルダを探す。
for _nm, _g in GROUP.items():
    _d = next((folders[norm(x)] for x in _g if norm(x) in folders), None)
    if _d:
        for x in _g: folders.setdefault(norm(x), _d)

# ★「メゾン・ド・アトラー宛て買取勧誘状」のように、題名が物件名＋用件になっていることがある。
#   末尾の部屋番号を落とした形でも引けるようにしておく。
for _k in list(folders):
    _s = re.sub(r"[0-9]+$", "", _k)
    if len(_s) >= 4: folders.setdefault(_s, folders[_k])


def canon(name):
    """呼び名を正式名称に直す。分からなければそのまま返す。"""
    return ALIAS.get(norm(name), N(str(name or "")))


def find_folder(name):
    k = norm(name)
    if k in folders: return folders[k]
    k2 = norm(canon(name))
    if k2 in folders: return folders[k2]
    cand = [v for kk, v in folders.items() if kk and (kk in k or k in kk) and min(len(kk), len(k)) >= 3]
    return max(cand, key=len) if cand else None

def safe(s):
    return re.sub(r'[/\\:*?"<>|]', "_", N(str(s))).strip()[:80]

# ---------- ★会社の壁: 新誠プロパティの物件は絶対に混ぜない ----------
# 大京商事の共有フォルダに新誠の物件の写真を置かない（逆も同じ）。
# フォルダが見つからないだけでは弱いので、新誠の物件名を明示的に弾く。
_c0 = sqlite3.connect(DB)
SHINSEI = set()
for (nm, al) in _c0.execute("SELECT name, aliases FROM shinsei_properties WHERE active=1"):
    SHINSEI.add(norm(nm))
    for a in re.split(r"[\n,、]", al or ""):
        if a.strip(): SHINSEI.add(norm(a.strip()))
_c0.close()

def is_shinsei(name):
    k = norm(name)
    if not k: return False
    if k in SHINSEI: return True
    return any(x and len(x) >= 3 and (x in k or k in x) for x in SHINSEI)

# ---------- 保存済みの記録 ----------
con = sqlite3.connect(DB)
con.execute("""CREATE TABLE IF NOT EXISTS patrol_photo_saved(
                 room_id INTEGER, file_id INTEGER, saved_path TEXT,
                 saved_at TEXT DEFAULT (datetime('now')),
                 PRIMARY KEY(room_id, file_id))""")
con.commit()
con.execute("""CREATE TABLE IF NOT EXISTS patrol_photo_skip(
                 room_id INTEGER, file_id INTEGER, reason TEXT,
                 at TEXT DEFAULT (datetime('now')), PRIMARY KEY(room_id,file_id))""")
con.commit()
# ★保存済み ＋ 「人が退避した＝もう要らない」もの を対象から外す。
#   退避したのに記録を消すと、次回また同じ写真が戻ってきてしまう（2026-09-05に実際に起きた）。
done = {(r[0], r[1]) for r in con.execute("SELECT room_id,file_id FROM patrol_photo_saved")}
done |= {(r[0], r[1]) for r in con.execute("SELECT room_id,file_id FROM patrol_photo_skip")}

# ---------- 実体がある画像を集める ----------
# ★中身が同じ画像は1枚しか保存しない（2026-09-05 オーナー判断）
#   同じ写真がChatworkへ二度投稿されると file_id が別になり、そのままだと
#   物件フォルダに同じ写真が2枚並ぶ（実際に8枚中8枚＝4組が重複していた）。
#   「間違って重複投稿したもの」なので記録としては1枚あれば足りる。
import hashlib
def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

items = []
for f in sorted(os.listdir(IMG)):
    if f.endswith(".json"): continue
    jp = os.path.join(IMG, f + ".json")
    if not os.path.exists(jp): continue
    j = json.load(open(jp))
    # ★古い .json は room_id / file_id を **文字列**で持っている。
    #   DB（patrol_photo_saved）は数値なので、そのまま比べると
    #   「保存済み」の判定が効かず、同じ写真を何度でも入れてしまう（2026-09-05）。
    try:
        rid, fid = int(j.get("room_id")), int(j.get("file_id"))
    except (TypeError, ValueError):
        continue
    row = con.execute("""SELECT property_name, title, description, created_at
                         FROM chatwork_images WHERE room_id=? AND file_id=?""", (rid, fid)).fetchone()
    if not row: continue
    prop, title, desc, created = row
    items.append({"file": f, "room_id": rid, "file_id": fid, "prop": prop,
                  "title": title or j.get("title") or "", "desc": desc or "", "created": created})

# ★同じ写真の .json が複数あることがある（AIが読み直すたびに増える）。
#   1枚につき1件にまとめる。まとめないと同じ写真を2回計画してしまう。
_uniq = {}
for _it in items:
    _uniq.setdefault((_it["room_id"], _it["file_id"]), _it)
items = list(_uniq.values())

print("=" * 72)
print(("【実行】" if GO else "【下見】") + f"  巡回写真の保存  （実体 {len(items)}枚）")
print("=" * 72)

plan, skip, ng = [], [], []
for it in items:
    if (it["room_id"], it["file_id"]) in done: skip.append(it); continue
    if not it["prop"]:
        # ★物件名の欄が空でも、タイトルが物件を指していることが多い
        #   （「ユーリムズビル 共用玄関エントランス」など）。タイトルから拾う。
        #   ただし新誠の物件を指していたら拾わない（会社の壁）。
        t = it["title"]
        if t and not is_shinsei(t) and find_folder(t):
            it["prop"] = canon(t)
            it["_src"] = "タイトルから読んだ"
        else:
            ng.append((it, "物件名が無い")); continue
    if is_shinsei(it["prop"]):
        ng.append((it, "★新誠プロパティの物件＝大京の共有フォルダには置かない")); continue
    # ★property_name と title が食い違うものは保存しない（2026-09-05 実測）
    #   84件中14組で食い違い、しかも title の方が正しかった。
    #   例: 物件名「K1ビル」/ title「ユーリムズハウス」→ 説明は3階建て住宅でK1ビルではない
    #       物件名「メゾンドール都島」/ title「トーヨーコーポ1F…電灯交換」
    #   このまま保存すると別の物件のフォルダに写真が入る。
    # ★比べる前に呼び名を正式名称へ直す。直さないと
    #   物件名「U-RIMS HOUSE」/ title「ユーリムズビル…」が食い違い扱いになる（2026-09-05）
    _p, _t = norm(canon(it["prop"])), norm(canon(it["title"]))
    _tf, _pf = find_folder(it["title"]), find_folder(it["prop"])
    if _tf and _pf and _tf == _pf:
        _t = _p                       # 同じ物件フォルダを指しているなら食い違いではない
    if _t and _p and _p[:4] not in _t and _t[:4] not in _p:
        ng.append((it, f"★物件名とタイトルが食い違う（title=「{it['title'][:24]}」）")); continue
    if is_shinsei(it["title"]):
        ng.append((it, "★タイトルが新誠の物件を指している")); continue
    d = find_folder(it["prop"])
    if not d: ng.append((it, "物件フォルダが無い（新誠の物件かも）")); continue
    day = (it["created"] or "")[:10] or datetime.date.today().isoformat()
    ext = os.path.splitext(it["file"])[1]
    name = f"{day}_{safe(it['title'] or it['prop'])}{ext}"
    dst = os.path.join(d, "記録・写真", "巡回", name)
    plan.append((it, dst))

# 中身が同じものは1枚だけ残す（先に来た方＝file_idが小さい方）
_seen = {}
_dedup = []
for it, dst in plan:
    h = _sha(os.path.join(IMG, it["file"]))
    if h in _seen:
        skip.append(it)                      # 重複投稿として保存しない
        continue
    _seen[h] = dst
    _dedup.append((it, dst))
plan = _dedup

# ★同じ題名で中身が違う写真は連番を振る（2026-09-05）
#   「ユーリムズハウス」という同じ題名の別の写真が2枚あり、
#   このままだと後の1枚が「同名だから中身も同じはず」と見なされて黙って消えていた。
_used = set()
_fixed = []
for it, dst in plan:
    src = os.path.join(IMG, it["file"])
    if dst not in _used and not os.path.exists(dst):
        _used.add(dst); _fixed.append((it, dst)); continue
    # ★既に同名がある。中身まで同じなら重ねない（同じ写真の再投稿）。
    #   違う写真のときだけ連番を振る。名前だけで判断すると別の写真が消える。
    if os.path.exists(dst) and _sha(dst) == _sha(src):
        skip.append(it); continue
    root, ext = os.path.splitext(dst)
    i = 2
    while True:
        cand = f"{root}-{i}{ext}"
        if cand in _used: i += 1; continue
        if os.path.exists(cand):
            if _sha(cand) == _sha(src): cand = None; break
            i += 1; continue
        break
    if cand is None: skip.append(it); continue
    _used.add(cand); _fixed.append((it, cand))
plan = _fixed

print(f"  保存する   {len(plan)}枚")
print(f"  保存済み   {len(skip)}枚")
print(f"  ★できない  {len(ng)}枚")
for it, why in ng:
    print(f"      [{why}] {it['prop'] or '（不明）'} / {it['title'][:34]}")
print()
for it, dst in plan:
    rel = dst.split("管理物件/")[-1]
    print(f"  {it['prop'][:20]:<22} → {rel[:74]}")

if not GO:
    print("\n  ※下見のみ。--go で実行"); sys.exit(0)

n = 0
for it, dst in plan:
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    if os.path.exists(dst):
        # 同名が既にある＝中身も同じはず（上でハッシュ重複は除いてある）。
        # file_id を付けて別名保存すると重複が増えるだけなので、記録だけ残して飛ばす。
        con.execute("INSERT OR REPLACE INTO patrol_photo_saved(room_id,file_id,saved_path) VALUES(?,?,?)",
                    (it["room_id"], it["file_id"], dst))
        continue
    shutil.copy2(os.path.join(IMG, it["file"]), dst)
    # ★説明の .txt は作らない（2026-09-05 オーナー判断）
    #   写真1枚につきテキストが1つ増えてフォルダが二重に見える。
    #   AIの説明文は chatwork_images.description に残っているので、
    #   検索が要るときはそちらを引けばよい。
    con.execute("INSERT OR REPLACE INTO patrol_photo_saved(room_id,file_id,saved_path) VALUES(?,?,?)",
                (it["room_id"], it["file_id"], dst))
    n += 1
con.commit()
print(f"\n  保存 {n}枚")
