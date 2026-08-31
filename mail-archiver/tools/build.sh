#!/bin/bash
# OCRの土台（macOS Vision）を作る。**このMacで1回叩けばよい**（成果物は git に入れない）。
#
#   ./tools/build.sh
#
# 作られるもの: tools/ocr_pdf … スキャンPDF・画像 → 文字（日本語＋英語）
# 必要なもの  : Xcode のコマンドラインツール（swiftc）。実測 2.5秒でビルドできる。
#
# ★もう1台のPCでも `attach_extract.py` を使うなら、そちらでもこれを1回実行すること
#   （バイナリは環境依存なので配らない）。ビルドしていない環境では OCR だけが
#   「土台が無い」と明示して落ちる＝黙ってテキスト無しとして記録しない。
set -eu
cd "$(dirname "$0")"
swiftc -O ocr_pdf.swift -o ocr_pdf
echo "できた: $(pwd)/ocr_pdf"
./ocr_pdf 2>&1 | head -1 || true
