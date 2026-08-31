#!/bin/bash
# 社内メールアーカイバの画面を開く（port 8538 / **127.0.0.1 固定**）。
#
#   ./run.sh
#
# ★画面のコードは複製していない。`mail-archiver/app.py` を、
#   **DB・保管先・名前だけ環境変数で差し替えて**動かす。
#   複製すると必ず分岐して、片方だけ直した状態になるため（社内で実際に起きた事故の型）。
#
# ★127.0.0.1 から動かさない。**社員のメール本文**を扱うので、社内LANにも出さない。
#   個人用のメールアーカイバ(8535)と同じ扱い。
set -u
cd "$(dirname "$0")" || exit 1

export MAIL_ARCHIVER_ENV="$PWD/.env.company-mail-archiver"
# ★社員ごとの設定は**このフォルダ**にある（mail-archiver 側を見に行かせない）
export MAIL_ARCHIVER_ENV_DIR="$PWD"
export MAIL_ARCHIVER_ENV_PREFIX=".env.company-mail-archiver."
export MAIL_ARCHIVER_DB="$PWD/local/company-mail.db"
export MAIL_ARCHIVER_DATA_DIR="${COMPANY_MAIL_STORE:-$HOME/Library/CloudStorage/Dropbox-個人/company-mail-archive}"

MA="$(cd .. && pwd)/mail-archiver"
[ -d "$MA" ] || { echo "mail-archiver が見つかりません: $MA"; exit 1; }

if [ ! -x "$MA/.venv/bin/python3" ]; then
  echo "mail-archiver の .venv がありません。先に $MA/run.sh を1度実行してください"
  exit 1
fi

exec "$MA/.venv/bin/python3" -m streamlit run "$MA/app.py" \
  --server.address 127.0.0.1 --server.port 8538 --server.headless true
