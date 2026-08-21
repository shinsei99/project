#!/usr/bin/env python3
"""公式書式フォルダを走査し、入力欄レジストリ(JSON)を作る。

openpyxl の全セル走査は1本あたり数秒かかるので、**毎回やらずにキャッシュする**。
アプリ起動時はこの JSON を読むだけにする。

使い方:
    .venv/bin/python scan_formats.py                # 既定の Dropbox 書類雛形を走査
    .venv/bin/python scan_formats.py <フォルダ>      # 任意のフォルダ
出力:
    data/format_registry.json
"""

import glob
import json
import os
import sys
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import docx_format_service as dfs  # noqa: E402
from services import field_map, official_format_service as ofs  # noqa: E402

DEFAULT_ROOT = os.path.expanduser(
    "~/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/"
    "（★必読★）新共有フォルダ/契約・書類/書類雛形"
)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "format_registry.json")


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_ROOT
    files = sorted(
        glob.glob(os.path.join(root, "**", "*.xlsx"), recursive=True)
        + glob.glob(os.path.join(root, "**", "*.docx"), recursive=True)
    )
    print("対象 {} 本".format(len(files)), flush=True)

    reg = []
    t0 = time.time()
    for i, f in enumerate(files, 1):
        rel = os.path.relpath(f, root)
        if os.path.basename(f).startswith("~$"):
            continue
        try:
            if f.lower().endswith(".docx"):
                targets = dfs.scan(f)
                fields = sorted(set(t["field"] for t in targets))
                reg.append({
                    "path": rel, "name": os.path.basename(f),
                    "category": rel.split(os.sep)[0], "kind": "docx",
                    "targets": targets, "fields": fields,
                })
                print("[%3d/%3d] %-52s Word 項目 %d" % (i, len(files), os.path.basename(f)[:52], len(fields)), flush=True)
                continue
            r = ofs.scan(f)
            mapping = field_map.resolve(r["inputs"])
            reg.append({
                "path": rel,
                "name": r["name"],
                "category": rel.split(os.sep)[0],
                "kind": "xlsx",
                "driver": r["driver"],
                "sheets": r["sheets"],
                "input_count": len(r["inputs"]),
                "fanout_count": sum(1 for x in r["inputs"] if x["fanout"]),
                "mapping": mapping,
                "unmapped": [k for k, _, _ in
                             [(a, b, c) for a, b, c in field_map.RULES]
                             if k not in mapping],
            })
            print("[%3d/%3d] %-52s %s" % (i, len(files), r["name"][:52],
                                          field_map.coverage(mapping)), flush=True)
        except Exception:
            print("[%3d/%3d] !! %s" % (i, len(files), rel), flush=True)
            traceback.print_exc()

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump({"root": root, "formats": reg}, fh, ensure_ascii=False, indent=1)
    print("\n書き出し: {}  ({} 本 / {:.1f}秒)".format(OUT, len(reg), time.time() - t0), flush=True)


if __name__ == "__main__":
    main()
