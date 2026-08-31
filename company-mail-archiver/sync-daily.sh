#!/bin/bash
# 社内メールの夜間取り込み（launchd から 00:30 に呼ばれる）。
#
#   取り込み → 英語メールの日本語訳 → 添付の中身（新着→積み残し）
#   → 意味検索のベクトル → 知識索引へ（大京商事）
#
# ★時間帯: **個人のメールアーカイバ(8535)と同じ00:30**（2026-08-31 オーナー指示で揃えた）。
#   もとは03:30だったが、そこは**共有フォルダOCR(03:00〜05:00)の真っ最中**で相性が悪かった。
#   00:30なら知識索引への書き込みが03:00より前に終わる。索引DBは互いに別ファイルなので
#   2つの取り込みが同時に走ってもロックは取り合わない。ただし**CPUは取り合う**ので、
#   添付の並列数はこちらを控えめ（既定2）にしてある。
#
# ★このアプリは**サーバーから1通も消さない**。他人のメールを消す操作を持たせない。
#   下で `--delete` を一切呼ばないだけでなく、設定に ARCHIVE_DELETE_ENABLED=1 が
#   混ざっていたら**取り込み自体を中止する**（事故は「うっかり書いた設定」から起きる）。
#
# ★launchd から起動されると PATH が空（git/python が見つからない）。[[reference_launchd_path_node]]
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
set -u
cd "$(dirname "$0")" || exit 1

LOG="local/sync-daily.log"
mkdir -p local

export MAIL_ARCHIVER_ENV="$PWD/.env.company-mail-archiver"
# ★社員ごとの設定は**このフォルダ**にある（mail-archiver 側を見に行かせない）
export MAIL_ARCHIVER_ENV_DIR="$PWD"
export MAIL_ARCHIVER_ENV_PREFIX=".env.company-mail-archiver."
export MAIL_ARCHIVER_DB="$PWD/local/company-mail.db"
export MAIL_ARCHIVER_DATA_DIR="${COMPANY_MAIL_STORE:-$HOME/Library/CloudStorage/Dropbox-個人/CLAUDE/company-mail-archive}"
MA="$(cd .. && pwd)/mail-archiver"

# ---- 安全弁（guards.py）。1つでも駄目なら**何もせずに止まる**
#   ・社員のメールをサーバーから消す設定になっていないか
#   ・原本や書き出しが会社の共有フォルダ配下になっていないか（全社員に見えてしまう）
if ! /usr/bin/python3 guards.py >> "$LOG" 2>&1; then
  echo "$(date '+%F %T') ★中止: 安全弁に引っかかった（上の行を見ること）" >> "$LOG"
  exit 1
fi

echo "===== $(date '+%F %T') 社内メール 取り込み開始 =====" >> "$LOG"
"$MA/.venv/bin/python3" "$MA/sync.py" --all-accounts --sync >> "$LOG" 2>&1
rc=$?

# --- 英語で届いたメールを日本語に訳す（個人用と揃える。2026-08-31 オーナー指示）---
# なぜ要るか: 埋め込みは多言語対応だが、**日本語で聞くと日本語メールが上位を埋め**、
#   英文メールは圏外に落ちる（個人用で実測）。日本語の訳文を持たせ、その訳文でベクトルを作ると
#   順位が戻り、全文検索でも日本語の語で英文メールが引っかかる。
# ★1晩の上限は個人用(100通)より控えめの50通。同じ00:30に個人用の翻訳も走るので、
#   **claudeの定額枠を2本で取り合う**ため。2026-08-27 に「翻訳が枠を使い切って
#   OCRを巻き添えにした」実績があるので欲張らない。TRANSLATE_MAX で変えられる。
# ★この段は**ベクトルより前**に置く。訳が付いてからベクトルを作らないと、
#   原文のままのベクトルが残って日本語で引けない（個人用は --retranslated で作り直している）。
# ★節約モード中は飛ばす（claudeの枠を使う工程）。~/.ai-quota-saver があれば節約モード
if "$HOME/ai-quota-saver.sh" check 2>/dev/null; then
  echo "----- $(date '+%F %T') 英語メールの翻訳は節約モードのため飛ばす -----" >> "$LOG"
else
  echo "----- $(date '+%F %T') 英語メールの日本語訳（新着分） -----" >> "$LOG"
  ( cd "$MA" && /usr/bin/python3 translate_english.py --limit "${TRANSLATE_MAX:-50}" ) >> "$LOG" 2>&1
fi

echo "----- $(date '+%F %T') 添付の中身（新着ぶん） -----" >> "$LOG"
/usr/bin/python3 "$MA/attach_extract.py" --since-days "${ATTACH_NEW_DAYS:-30}" \
    --workers "${ATTACH_WORKERS:-2}" >> "$LOG" 2>&1

echo "----- $(date '+%F %T') 添付の中身（積み残し・小分け） -----" >> "$LOG"
/usr/bin/python3 "$MA/attach_extract.py" --max-minutes "${ATTACH_MAX_MIN:-30}" \
    --workers "${ATTACH_WORKERS:-2}" >> "$LOG" 2>&1

# --- 意味検索のベクトルを作る（個人用と揃える。2026-08-31）---
# なぜ要るか: 画面には「ベクトル検索（意味）」があるのに、ベクトルが無いと使えない。
#   個人用(8535)と同じ `.venv-embed`（torch入り）を借りる。DBは環境変数で社内用を指している。
#   ★閲覧UIには torch を載せない設計なので、この専用venvから呼ぶ（個人用と同じ流儀）。
if [ -x "$MA/.venv-embed/bin/python" ]; then
  echo "----- $(date '+%F %T') 意味検索ベクトルの追加 -----" >> "$LOG"
  ( cd "$MA" && ./.venv-embed/bin/python embed_backfill.py ) >> "$LOG" 2>&1
  # 訳が付いたものは**訳文で作り直す**（原文のままだと日本語で引けない。個人用と同じ）
  ( cd "$MA" && ./.venv-embed/bin/python embed_backfill.py --retranslated ) >> "$LOG" 2>&1
fi

# ---- AI業務マネージャー（大京商事）の知識索引へ
# ★会社の壁: export_to_knowledge.py が company='大京商事株式会社' を必ず渡す。
echo "----- $(date '+%F %T') 知識索引へ反映（大京商事） -----" >> "$LOG"
/usr/bin/python3 export_to_knowledge.py --since-days "${KB_SINCE_DAYS:-365}" >> "$LOG" 2>&1

echo "----- $(date '+%F %T') 終了 sync_rc=$rc -----" >> "$LOG"
exit $rc
