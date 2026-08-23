#!/bin/bash
# AI重説アシスタント（開発中・port 8536・127.0.0.1 固定）
# 注意: --server.address を省略すると Streamlit の既定は 0.0.0.0（＝LANに公開）。必ず明示する。
# 開発中かつ案件の個人情報を扱うので、完成するまで社内LANには出さない。
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
exec .venv/bin/streamlit run app.py --server.port 8536 --server.headless true --server.address 127.0.0.1
