# -*- coding: utf-8 -*-
"""GoogleドライブのURLから、このMacにある実体の場所を割り出す Tool。

**なぜ要るか**
  オーナーはチャットに Drive の URL を貼って「この物件です」「この資料どうですか」と
  投げてくる。AIがその URL を素直に取りに行くと **401（要認証）で必ず失敗する**。
  Drive は非公開なので、外から HTTP で叩いても中身は取れない。

**どうやって解くか（2026-08-31 に方式変更）**
  Google Drive for Desktop が持つ**ローカルの索引データベース**を引く。

      ~/Library/Application Support/Google/DriveFS/<数字>/metadata_sqlite_db
        items          … stable_id / id(DriveのID) / local_title / is_folder / trashed
        stable_parents … 親子関係。たどれば完全なパスが組める

  ★最初は「フォルダの拡張属性 com.google.drivefs.item-id を1件ずつ照合」する方式で
    作ったが、**2つの理由で失敗した**。
      1. 遅い。CloudStorage 全体で9分かけても終わらなかった。
      2. **取りこぼす。** Drive は同じフォルダに複数のIDを持たせることがある
         （作り直し・移動の履歴で古いIDと新しいIDが両方生きる）。拡張属性から読める
         IDは1つだけなので、オーナーが貼ったURLのIDと一致せず「存在しません」と
         誤答した。実際に SBP福島北 でこれが起き、「同期されていない別フォルダ」と
         いう誤った説明までしてしまった。
    索引DBは Drive が持つ全IDを知っているので、この取りこぼしが起きない。

**会社の壁**
  返す場所は、いまの会社の資料ルートの中だけ。ルート外なら場所も名前も返さない。
  これをやらないと「URLさえ知っていれば他社の資料の場所が分かる」抜け道になる。
"""
import glob
import os
import re
import shutil
import sqlite3
import tempfile

from services import company_scope as CS

DRIVEFS = os.path.expanduser("~/Library/Application Support/Google/DriveFS")
_ID_RE = re.compile(r"/(?:folders|d)/([A-Za-z0-9_\-]{10,})|[?&]id=([A-Za-z0-9_\-]{10,})")


def _ids(text: str):
    out = []
    for m in _ID_RE.finditer(text or ""):
        i = m.group(1) or m.group(2)
        if i and i not in out:
            out.append(i)
    return out


def _open_db():
    """索引DBの読み取り専用コピーを開く。

    ★原本を直に開かない。Drive が書き込み中の DB を触るとロックで詰まる。
      -wal / -shm ごとコピーして、書きかけの内容も含めて読む。
    """
    hits = sorted(glob.glob(os.path.join(DRIVEFS, "*", "metadata_sqlite_db")))
    if not hits:
        return None, "Google Drive for Desktop の索引が見つかりません"
    src = hits[-1]
    tmp = os.path.join(tempfile.mkdtemp(prefix="drivefs-"), "db")
    try:
        shutil.copy2(src, tmp)
        for ext in ("-wal", "-shm"):
            if os.path.exists(src + ext):
                shutil.copy2(src + ext, tmp + ext)
        con = sqlite3.connect(tmp)
        con.row_factory = sqlite3.Row
        return con, None
    except Exception as e:
        return None, f"索引を読めません: {type(e).__name__}: {e}"


def _allowed_roots():
    from services import config
    roots = []
    if CS.is_default_company():
        r = config.get("knowledge_source_dir")
        if r:
            roots.append(os.path.abspath(r))
    r = CS.source_root()
    if r:
        roots.append(os.path.abspath(r))
    return roots


def _path_of(con, stable_id, depth=0):
    """親をたどって「/マイドライブ/…」の形にする。"""
    if depth > 20:
        return ""
    row = con.execute("SELECT parent_stable_id FROM stable_parents WHERE item_stable_id=?",
                      (stable_id,)).fetchone()
    if not row:
        return ""
    par = con.execute("SELECT stable_id, local_title FROM items WHERE stable_id=?",
                      (row["parent_stable_id"],)).fetchone()
    if not par:
        return ""
    return _path_of(con, par["stable_id"], depth + 1) + "/" + (par["local_title"] or "?")


def _local_path(drive_path):
    """Drive上のパス（/マイドライブ/…）を、このMacの絶対パスに直す。"""
    base = sorted(glob.glob(os.path.expanduser(
        "~/Library/CloudStorage/GoogleDrive-*")))
    if not base:
        return ""
    return os.path.join(base[-1], drive_path.lstrip("/"))


def drive_resolve(url: str, limit: int = 40):
    """GoogleドライブのURL（複数可）から、このMacにある場所を割り出す。

    ★URLを直接開こうとしないこと。非公開なので401になる。必ずこれで場所に直してから読む。
    """
    ids = _ids(url)
    if not ids:
        return {"ok": False,
                "error": "URLからIDを取り出せません。"
                         "https://drive.google.com/drive/folders/<ID> の形か確認してください。"}
    roots = _allowed_roots()
    if not roots:
        return CS.deny(what="Googleドライブの資料")
    con, err = _open_db()
    if err:
        return {"ok": False, "error": err}

    out = []
    for i in ids:
        r = con.execute(
            "SELECT stable_id, local_title, is_folder, trashed, is_owner "
            "FROM items WHERE id=?", (i,)).fetchone()
        if not r:
            out.append({"id": i, "found": False,
                        "note": "Googleドライブの索引にありません（削除済み、または別アカウント）"})
            continue
        dpath = _path_of(con, r["stable_id"]) + "/" + (r["local_title"] or "")
        path = _local_path(dpath)
        if not any(os.path.abspath(path) == x or os.path.abspath(path).startswith(x + os.sep)
                   for x in roots):
            out.append({"id": i, "found": False,
                        "note": "別の会社のものなので、ここからは扱えません"})
            continue
        item = {"id": i, "found": True, "name": r["local_title"], "path": path,
                "is_dir": bool(r["is_folder"]), "trashed": bool(r["trashed"]),
                "on_disk": os.path.exists(path)}
        if r["is_folder"]:
            kids = con.execute(
                "SELECT i.local_title, i.is_folder FROM stable_parents sp "
                "JOIN items i ON i.stable_id = sp.item_stable_id "
                "WHERE sp.parent_stable_id=? AND i.trashed=0 ORDER BY i.local_title",
                (r["stable_id"],)).fetchall()
            item["files"] = len(kids)
            item["contents"] = [("📁 " if k["is_folder"] else "") + (k["local_title"] or "")
                                for k in kids[:limit]]
            if len(kids) > limit:
                item["contents_more"] = len(kids) - limit
        elif os.path.exists(path):
            item["size"] = os.path.getsize(path)
        out.append(item)
    con.close()
    return {"ok": True, "items": out}
