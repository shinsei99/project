#!/usr/bin/env python3
"""共有フォルダの棚卸しExcel「全ファイル一覧.xlsx」を作り直す。

**なぜこれがあるか（2026-08-30 作成）**
  この一覧は 2026-07-22 を最後に更新が止まっていた。オーナーの認識は
  「定期的に自動で作り直してもらっている」だったが、**作る側の仕組みは
  リポジトリにもDropboxにも存在しなかった**（列名・ファイル名で全体を探して0件）。
  人の手か外部の手で作られていたと思われる。これで本当に自動化できる。

**なぜ chatwork-ai-manager にあるか（2026-09-03 に file-finder から移設）**
  元は横断ファイル検索（file-finder・8520）の付属だったが、そのアプリを廃止した
  （AI業務マネージャーの `kb_search` / `find_files` が同じことをするため）。
  ただし**この棚卸しだけは廃止できない**。作られる `全ファイル一覧.xlsx` は
    1. AI業務マネージャーの知識索引に取り込まれている（毎晩の refresh）
    2. `find_files` ツールの元データ
    3. **全社員が共有フォルダで直接開いている実物**
  の3役を兼ねている。**消費者がここになったので、ここに置く。**

**出力の形は既存のExcelに合わせてある**（列やシートの形を変えると索引側が崩れる）:
  - 共有フォルダの**トップ階層のフォルダごとに1シート**
  - 列: 種別 / フルパス / 名前 / 親フォルダ / 階層 / 拡張子 / サイズ / サイズ(bytes) / 更新日時
  - フルパス・親フォルダは**そのシート（カテゴリ）から見た相対パス**
  - サイズは 2進換算で `9 B` / `45.5 KB` / `303.0 MB` の形
  - 隠しファイル（`.DS_Store` など）は入れない（既存Excelにも0件）

**使い方**
  python3 build_inventory.py             # chatwork-ai-manager/data/ にだけ書く（下見）
  python3 build_inventory.py --publish   # 共有フォルダの実物も置き換える

★ --publish は**全社員が見るファイル**を置き換える。先に下見で件数を確かめること。
"""
from __future__ import annotations

import argparse
import datetime
import pathlib
import shutil
import sys
import unicodedata

import openpyxl

SHARE = pathlib.Path(
    "/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ")
LOCAL = pathlib.Path("/Users/apple/chatwork-ai-manager/data/全ファイル一覧.xlsx")
PUBLISHED = SHARE / "全ファイル一覧.xlsx"
def nfc(s: str) -> str:
    """★macOSのファイル名は分解形(NFD)で返る（「ブ」が「フ」+濁点になる）。

    そのまま書くと、既存のExcel（NFC）と別の文字列になり、
    シート名が一致しない・他の道具で突き合わせられない、といったことが起きる。
    **保存する値は NFC に揃えておく**（実測で 2026-08-30 に気づいた）。
    ここが崩れると kb_search / find_files が濁点つきの名前を拾えなくなる。
    """
    return unicodedata.normalize("NFC", s)


HEAD = ["種別", "フルパス", "名前", "親フォルダ", "階層", "拡張子", "サイズ", "サイズ(bytes)", "更新日時"]


def human(n: int) -> str:
    """既存Excelと同じ表記（2進換算・小数1桁。1KB未満は整数＋B）。"""
    if n < 1024:
        return f"{n} B"
    for unit, div in (("KB", 1024), ("MB", 1024 ** 2), ("GB", 1024 ** 3)):
        v = n / div
        if v < 1024 or unit == "GB":
            return f"{v:.1f} {unit}"
    return f"{n} B"


def walk(base: pathlib.Path, rel: pathlib.Path, depth: int, rows: list, skipped: list) -> None:
    """1フォルダぶん。**名前順で、フォルダもファイルも混ぜて並べる**（既存Excelと同じ並び）。"""
    try:
        entries = sorted(( base / rel).iterdir(), key=lambda p: p.name)
    except OSError as e:
        skipped.append((str(rel), str(e)))
        return
    for p in entries:
        if p.name.startswith("."):          # .DS_Store など
            continue
        r = rel / p.name if str(rel) != "." else pathlib.Path(p.name)
        try:
            st = p.stat()
        except OSError as e:                 # オンラインのみ等で読めないものは飛ばして記録する
            skipped.append((str(r), str(e)))
            continue
        mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
        parent = str(r.parent) if str(r.parent) != "." else ""
        if p.is_dir():
            rows.append(["フォルダ", nfc(str(r)), nfc(p.name), nfc(parent), depth, "", "", "", mtime])
            walk(base, r, depth + 1, rows, skipped)
        else:
            ext = p.suffix[1:].lower() if p.suffix else ""
            rows.append(["ファイル", nfc(str(r)), nfc(p.name), nfc(parent), depth,
                         ext, human(st.st_size), st.st_size, mtime])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true", help="共有フォルダの実物も置き換える")
    args = ap.parse_args()

    if not SHARE.exists():
        print(f"★共有フォルダが読めない: {SHARE}", file=sys.stderr)
        return 1

    cats = sorted((p for p in SHARE.iterdir() if p.is_dir() and not p.name.startswith(".")),
                  key=lambda p: p.name)
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    total = 0
    skipped: list = []
    print("=== 作り直し ===")
    for c in cats:
        rows: list = []
        walk(c, pathlib.Path("."), 1, rows, skipped)
        ws = wb.create_sheet(title=nfc(c.name)[:31])
        ws.append(HEAD)
        for r in rows:
            ws.append(r)
        nf = sum(1 for r in rows if r[0] == "ファイル")
        print(f"  {c.name:26s} {len(rows):6,} 行（ファイル {nf:,} / フォルダ {len(rows)-nf:,}）")
        total += len(rows)
    print(f"  {'合計':26s} {total:6,} 行")
    if skipped:
        print(f"\n★読めなかったもの {len(skipped)} 件（オンラインのみ等）")
        for s, e in skipped[:5]:
            print(f"    {s[:70]} … {e[:40]}")

    LOCAL.parent.mkdir(parents=True, exist_ok=True)
    wb.save(LOCAL)
    print(f"\n書き出した（下見）: {LOCAL}  {LOCAL.stat().st_size // 1024} KB")

    if args.publish:
        # ★置き換える前に、いまの実物を控える（戻せるように）。
        #   控えは**共有フォルダに置かない**（社員が「どっちを開くのか」と迷うため）。
        #   Dropbox 側にも30日分の版が残る。
        if PUBLISHED.exists():
            # ★控えは共有フォルダの _アーカイブ へ入れる（オーナー指示 2026-08-30）。
            #   直下に置くと社員が「どっちを開くのか」と迷う。アーカイブなら
            #   「1年以上使われていないものの一時退避」という既存の決まりに沿う。
            _arc = SHARE / "_アーカイブ（2027年7月削除予定）"
            _arc.mkdir(parents=True, exist_ok=True)
            bak = _arc / f"全ファイル一覧_{datetime.datetime.now():%Y%m%d}_旧.xlsx"
            # ★同じ日に2回流したとき、**前に取った控えを上書きしない**。
            #   上書きすると「置き換える前の版」ではなく「さっき自分が置いた版」が
            #   控えとして残り、戻せなくなる（2026-08-30 に気づいて塞いだ）。
            if bak.exists():
                print(f"今日の控えは既にある（上書きしない）: {bak.name}")
                bak = None
            else:
                shutil.copy2(PUBLISHED, bak)
            if bak:
                print(f"いまの実物を控えた（アーカイブ）: {bak.name}")
        shutil.copy2(LOCAL, PUBLISHED)
        print(f"共有フォルダを置き換えた: {PUBLISHED}")
    else:
        print("※ 共有フォルダは触っていない（置き換えるには --publish）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
