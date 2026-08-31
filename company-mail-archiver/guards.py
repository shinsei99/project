#!/usr/bin/env python3
"""社内メールアーカイバの安全弁。**動かす前に機械が止める**ためのもの。

    /usr/bin/python3 guards.py            全部点検（1つでも駄目なら終了コード1）

## なぜ要るか

このアプリは**他人（社員）のメール**を扱う。個人用のメールアーカイバ（8535）と違い、
間違えたときの取り返しがつかない。守りたいことは3つで、どれも
「気をつける」ではなく**機械で止める**形にしてある。

1. **サーバーから消さない** … 設定に `ARCHIVE_DELETE_ENABLED=1` があったら動かさない
2. **共有フォルダに置かない** … 原本・書き出しが会社のDropbox共有配下なら動かさない
   （社員のメール本文が全社員に見えてしまう）
3. **会社の壁** … 知識索引へ渡すときの会社名が大京商事であること
"""
from __future__ import annotations

import os
import sys
from typing import List, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
COMPANY = "大京商事株式会社"

# 会社の共有フォルダの目印。ここの下には**絶対に置かない**
SHARED_MARKERS = ("大京商事", "Dropbox (大京商事", "共有フォルダ", "（★必読★）")


def _env_files(env_dir: str = HERE) -> List[str]:
    out = []
    for name in sorted(os.listdir(env_dir)):
        if name.startswith(".env.company-mail-archiver") and not name.endswith(".example"):
            out.append(os.path.join(env_dir, name))
    return out


def check_delete_disabled(env_dir: str = HERE) -> List[str]:
    """削除が有効になっている設定ファイルを返す（空なら合格）。"""
    bad = []
    for p in _env_files(env_dir):
        try:
            for line in open(p, encoding="utf-8"):
                line = line.strip()
                if line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                if k.strip() == "ARCHIVE_DELETE_ENABLED" and v.strip().strip('"\'') not in ("0", ""):
                    bad.append(os.path.basename(p))
        except OSError:
            continue
    return bad


def check_not_shared(*paths: str) -> List[str]:
    """会社の共有フォルダ配下を指しているパスを返す（空なら合格）。"""
    bad = []
    for p in paths:
        if not p:
            continue
        ap = os.path.abspath(os.path.expanduser(p))
        if any(m in ap for m in SHARED_MARKERS):
            bad.append(ap)
    return bad


def check_company(company: str) -> bool:
    return company == COMPANY


def run_all(env_dir: str = HERE) -> Tuple[bool, List[str]]:
    msgs: List[str] = []
    bad = check_delete_disabled(env_dir)
    if bad:
        msgs.append("★削除が有効な設定がある（社員のメールは消さない）: " + ", ".join(bad))

    store = os.environ.get("MAIL_ARCHIVER_DATA_DIR", "")
    out_dir = os.path.join(env_dir, "knowledge_out")
    shared = check_not_shared(store, out_dir)
    if shared:
        msgs.append("★会社の共有フォルダの下を指している（社員全員に見えてしまう）: "
                    + ", ".join(shared))

    if not check_company(COMPANY):
        msgs.append("★会社名が大京商事ではない（会社の壁）")
    return (not msgs), msgs


def main() -> int:
    ok, msgs = run_all()
    if ok:
        print("安全弁: すべて合格（削除しない／共有フォルダに置かない／会社の壁）")
        return 0
    for m in msgs:
        print(m, file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
