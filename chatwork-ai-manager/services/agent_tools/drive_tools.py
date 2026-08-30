# -*- coding: utf-8 -*-
"""Googleドライブの共有リンクから、このMacにある実体の場所を割り出す Tool。

**なぜ要るか**
  オーナーはチャットに Drive の URL を貼って「この物件です」「この資料どうですか」と
  投げてくる。AIがその URL を素直に取りに行くと **401（要認証）で必ず失敗する**。
  Drive は非公開なので、外から HTTP で叩いても中身は取れない。
  2026-08-31 に「またドライブのURLを認識できなくなってる」と指摘された。

**どうやって解くか**
  Google Drive for Desktop は、同期した各ファイル・フォルダの拡張属性に
  Drive の ID を持っている。

      xattr -p "com.google.drivefs.item-id#S" <パス>   → 0ByjHeFRK2W-YSDFrU0R4STFCaE0

  URL から ID を取り出し、CloudStorage 配下を歩いて突き合わせれば、
  ローカルの絶対パスが分かる。あとは普通のファイルとして読める。

**会社の壁**
  返す場所は、いまの会社の資料ルートの中だけに限る。
  ルート外を指していたら場所を教えない（company_scope）。
  これをやらないと「URLさえ知っていれば他社の資料の場所が分かる」抜け道になる。
"""
import os
import re
import subprocess

from services import company_scope as CS

CLOUD = os.path.expanduser("~/Library/CloudStorage")
XATTR = "com.google.drivefs.item-id#S"

# https://drive.google.com/drive/folders/<ID>?...  /  /file/d/<ID>/view  /  ?id=<ID>
_ID_RE = re.compile(r"/(?:folders|d)/([A-Za-z0-9_\-]{10,})|[?&]id=([A-Za-z0-9_\-]{10,})")


def _ids(text: str):
    out = []
    for m in _ID_RE.finditer(text or ""):
        i = m.group(1) or m.group(2)
        if i and i not in out:
            out.append(i)
    return out


def _item_ids(paths):
    """まとめて拡張属性を引く。path -> Drive の item-id。

    ★1件ずつ `xattr` を起動すると桁違いに遅い（CloudStorage 全体で9分かけても
      終わらなかった・2026-08-31 実測）。`xattr -p <属性> <file...>` は複数の
      ファイルを一度に受けて「パス: 値」で返すので、まとめて渡す。
      macOS には os.getxattr が無く（Linux専用）、xattr モジュールも入っていない。
    """
    out = {}
    B = 400                       # 引数の長さ上限に当たらない程度でまとめる
    for i in range(0, len(paths), B):
        chunk = paths[i:i + B]
        try:
            r = subprocess.run(["xattr", "-p", XATTR] + chunk,
                               capture_output=True, text=True, timeout=60)
        except Exception:
            continue
        for line in r.stdout.splitlines():
            # 値そのものに ": " は入らないので右から1回だけ割る…ではなく、
            # パスに ": " が入り得るので**属性値は最後のトークン**として取る
            if ": " not in line:
                continue
            path, _, val = line.rpartition(": ")
            v = val.strip()
            if v:
                out[path] = v
        if len(chunk) == 1 and r.stdout and ": " not in r.stdout:
            # ファイルが1つだけのときはパスを付けずに値だけ返る
            out[chunk[0]] = r.stdout.strip()
    return out


def _allowed_roots():
    """いまの会社が見てよいルート。既定の会社は共有フォルダ、他社は自社ルート。"""
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


def _inside(path: str, roots) -> bool:
    p = os.path.abspath(path)
    return any(p == r or p.startswith(r + os.sep) for r in roots)


def drive_resolve(url: str, limit: int = 40):
    """Googleドライブの共有リンク（複数可）から、このMacにある場所を割り出す。

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

    want = {i: None for i in ids}
    scanned = 0
    # ★歩くのは「いまの会社が見てよいルート」の中だけ。CloudStorage 全体を歩くと
    #   遅すぎて実用にならないうえ、他社のフォルダまで舐めることになる。
    for base in roots:
        batch = []
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in dirnames + filenames:
                if not name.startswith("."):
                    batch.append(os.path.join(dirpath, name))
            if len(batch) >= 2000:
                scanned += len(batch)
                for path, i in _item_ids(batch).items():
                    if i in want and want[i] is None:
                        want[i] = path
                batch = []
                if all(v is not None for v in want.values()):
                    break
        if batch:
            scanned += len(batch)
            for path, i in _item_ids(batch).items():
                if i in want and want[i] is None:
                    want[i] = path
        if all(v is not None for v in want.values()):
            break

    out = []
    for i, p in want.items():
        if not p:
            out.append({"id": i, "found": False,
                        "note": "このMacに同期されていないか、まだ取り込まれていません"})
            continue
        if not _inside(p, roots):
            # ★他社のものだった場合、場所も名前も教えない
            out.append({"id": i, "found": False,
                        "note": "別の会社のものなので、ここからは扱えません"})
            continue
        item = {"id": i, "found": True, "path": p, "name": os.path.basename(p),
                "is_dir": os.path.isdir(p)}
        if item["is_dir"]:
            names = sorted(x for x in os.listdir(p) if not x.startswith("."))
            item["files"] = len([1 for r, _, fs in os.walk(p)
                                 for x in fs if not x.startswith(".")])
            item["contents"] = names[:limit]
            if len(names) > limit:
                item["contents_more"] = len(names) - limit
        else:
            item["size"] = os.path.getsize(p)
        out.append(item)
    return {"ok": True, "scanned": scanned, "items": out}
