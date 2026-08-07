# -*- coding: utf-8 -*-
"""スマホから送った写真の受け取り口。

倉庫でスマホから「経理2014-1」のようなフォルダを作って写真を入れておくと、
Dropbox / iCloud Drive 経由でMacに同期され、「📥 ファイルを登録」タブに出てくる。

**フォルダ1つ＝クリアファイル1冊**。フォルダ名がそのまま台帳の見出しになる。
撮った写真はそのまま `ai_reader` に渡すので、ここでは画像を加工しない
（向き補正は ai_reader → pdf_orient が受け持つ）。
"""

from __future__ import annotations

import os
import shutil

EXTS = {".pdf", ".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp"}


def default_root() -> str:
    """既定の取り込みフォルダ。**個人のDropbox**を優先する。

    スマホ（書類おくる）側は個人アカウントでDropboxにつなぐ運用にしているため
    （会社のBusinessアカウントだとサードパーティアプリに管理者承認が要る）。
    """
    home = os.path.expanduser("~")
    for cand in (
        os.path.join(home, "Library/CloudStorage/Dropbox-個人", "書類取込"),
        os.path.join(home, "Dropbox", "書類取込"),
        os.path.join(home, "Library/CloudStorage/Dropbox-大京商事　株式会社", "書類取込"),
        os.path.join(home, "Library/Mobile Documents/com~apple~CloudDocs", "書類取込"),
    ):
        if os.path.isdir(os.path.dirname(cand)):
            return cand
    return os.path.join(home, "Documents", "書類取込")


def list_folders(root: str) -> list:
    """取り込みフォルダ直下のサブフォルダを「1冊ぶん」として一覧する。"""
    out = []
    if not root or not os.path.isdir(root):
        return out
    for name in sorted(os.listdir(root)):
        if name.startswith(".") or name.startswith("_"):
            continue  # _done などの作業用は出さない
        d = os.path.join(root, name)
        if not os.path.isdir(d):
            continue
        files = sorted(
            f for f in os.listdir(d)
            if not f.startswith(".") and os.path.splitext(f)[1].lower() in EXTS
        )
        if files:
            out.append({"name": name, "path": d, "files": files})
    return out


def read_files(entry: dict) -> list:
    """1冊ぶんの写真を (bytes, ファイル名) のリストで返す。ai_reader にそのまま渡せる。"""
    uploads = []
    for f in entry["files"]:
        with open(os.path.join(entry["path"], f), "rb") as fh:
            uploads.append((fh.read(), f))
    return uploads


def archive(entry: dict) -> str:
    """読み終わったフォルダを `_done/` へ移す（**消さない**）。移動先を返す。"""
    root = os.path.dirname(entry["path"])
    done = os.path.join(root, "_done")
    os.makedirs(done, exist_ok=True)
    dest = os.path.join(done, entry["name"])
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(done, f"{entry['name']}_{n}")
        n += 1
    shutil.move(entry["path"], dest)
    return dest
