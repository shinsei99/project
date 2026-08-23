#!/bin/bash
# 送付書ジェネレーター（**個人専用**・port 8518）
# 社員が使うのは「送付書メーカー」(8525)。こちらは差出人を4プロファイルから選べる個人用なので、
# 注意: --server.address を省略すると Streamlit の既定は 0.0.0.0（＝LANに公開）。必ず明示する。
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
fi
exec .venv/bin/streamlit run app.py --server.port 8518 --server.headless true --server.address 127.0.0.1
