#!/usr/bin/env python3
"""旧Word（.doc）を .docx に変換する。**表を壊さずに**。

    .venv/bin/python doc2docx.py <ファイルまたはフォルダ> [...]
    .venv/bin/python doc2docx.py --dry-run <フォルダ>     # 変換せず対象だけ出す

## なぜ自前でやるのか（2026-08-21 に一通り試した結果）

| 手段 | 結果 |
|---|---|
| Word の AppleScript `save as` | **使えない**。3通り試して全て `-1708 メッセージを認識できません` |
| `textutil -convert docx` | **表が壊れる**。docx書き出し側の問題（表15個→0個を実測） |
| `textutil -convert rtf` | **表は残る**（RTFはOK） |
| `pandoc -f rtf -t docx` | **表が残る**。ただし後述の文字化けあり |

→ 採用したのは **textutil で RTF にして pandoc で docx にする** 2段構え。

## 文字化けへの対処

textutil が出す RTF は `\\ansicpg932`（Shift-JIS）を名乗り、一部の文字を
`\\'xx` の生バイトで埋め込む。pandoc は cp932 を解釈できず
（`Unsupported code page 932`）、その部分だけラテン文字に化ける
（実測: 「年月日」が `”NŒŽ“ú` になった）。

本文の大半は既に `\\uNNNN` の Unicode エスケープになっているので、
**残った `\\'xx` の連なりだけを CP932 として解釈し直し、`\\uNNNN` に書き換える**。
実測した承諾書では該当は16バイトだけだった。
"""

from __future__ import annotations

import glob
import os
import re
import subprocess
import sys
import tempfile

_HEX_RUN = re.compile(rb"(?:\\'[0-9a-fA-F]{2})+")


def _to_unicode_escapes(rtf: bytes) -> tuple[bytes, int]:
    """RTF 内の `\\'xx` 連続を CP932 として解釈し `\\uNNNN` に置き換える。

    戻り値は (変換後, 置換したバイト数)。
    RTF の `\\uNNNN` は 16bit 符号付きなので 32767 を超える値は負数で書く決まり。
    直後に代替文字を1つ置く作法に従って `?` を付ける。
    """
    replaced = 0

    def sub(m: "re.Match[bytes]") -> bytes:
        nonlocal replaced
        raw = bytes(int(h, 16) for h in re.findall(rb"\\'([0-9a-fA-F]{2})", m.group(0)))
        try:
            text = raw.decode("cp932")
        except UnicodeDecodeError:
            return m.group(0)  # 解釈できないものは触らない
        replaced += len(raw)
        out = []
        for ch in text:
            code = ord(ch)
            if code > 32767:
                code -= 65536
            out.append(("\\u%d?" % code).encode("ascii"))
        return b"".join(out)

    return _HEX_RUN.sub(sub, rtf), replaced


def convert(src: str, dst: str = "") -> str:
    """1本を変換して出力パスを返す。既定の出力先は同じ場所の .docx。"""
    if not src.lower().endswith(".doc"):
        raise ValueError("対象は .doc のみ: %s" % src)
    dst = dst or os.path.splitext(src)[0] + ".docx"

    with tempfile.TemporaryDirectory() as tmp:
        rtf = os.path.join(tmp, "mid.rtf")
        subprocess.run(["textutil", "-convert", "rtf", "-output", rtf, src], check=True)

        with open(rtf, "rb") as fh:
            data = fh.read()
        data, n = _to_unicode_escapes(data)
        with open(rtf, "wb") as fh:
            fh.write(data)

        proc = subprocess.run(
            ["pandoc", "-f", "rtf", "-t", "docx", "-o", dst, rtf],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError("pandoc 失敗: %s" % proc.stderr.strip()[:200])
    return dst


def _targets(paths) -> list:
    out = []
    for p in paths:
        if os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, "**", "*.doc"), recursive=True))
        elif p.lower().endswith(".doc"):
            out.append(p)
    return [p for p in out if not os.path.basename(p).startswith("~$")]


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--dry-run"]
    dry = "--dry-run" in sys.argv
    if not args:
        print(__doc__)
        return 1

    files = _targets(args)
    print("対象 %d 本%s" % (len(files), "（--dry-run のため変換しない）" if dry else ""))
    ok = ng = 0
    for f in files:
        if dry:
            print("  %s" % os.path.basename(f))
            continue
        try:
            dst = convert(f)
            print("  ✓ %-46s → %s" % (os.path.basename(f)[:46], os.path.basename(dst)))
            ok += 1
        except Exception as e:
            print("  ✗ %-46s %s" % (os.path.basename(f)[:46], e))
            ng += 1
    if not dry:
        print("\n成功 %d / 失敗 %d" % (ok, ng))
    return 0 if ng == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
