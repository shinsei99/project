#!/bin/bash
# AI重説アシスタント（不動産・完成・port 8536・社内LAN共有）
#
# 注意: --server.address を省略すると Streamlit の既定は 0.0.0.0（＝LANに公開）。必ず明示する。
#
# 2026-08-27 に開発中→完成へ移行し、**メインPCでのみ** 0.0.0.0（社内LAN共有）にした。
# **サブPCでこれをそのまま叩くと社内LANに二重公開される。** サブPCで動きを見るときは
#   .venv/bin/streamlit run app.py --server.port 8536 --server.address 127.0.0.1
# のように 127.0.0.1 を明示して起動すること（CLAUDE.md「バインド先のルール」）。
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
# 公式書式200本のレジストリ（Dropbox の「契約・書類/書類雛形」を走査した結果）。
# git には入らない（案件名を含むため）ので、無ければここで作る。
if [ ! -f data/format_registry.json ]; then
  echo "書式レジストリが無いので作ります（scan_formats.py）…"
  .venv/bin/python scan_formats.py || echo "※ 走査に失敗。Dropbox の書類雛形フォルダを確認してください"
fi
exec .venv/bin/streamlit run app.py --server.port 8536 --server.headless true --server.address 0.0.0.0
