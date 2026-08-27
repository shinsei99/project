#!/bin/bash
# 毎日の自動取り込み（launchd から午前2時に呼ばれる）。
# ★ /bin/bash 経由で呼ぶこと。保管先が個人Dropbox（CloudStorage）で、
#   launchd 常時起動プロセスは責任プロセスに FDA が無いと読み書きできない。
#   このMacは /bin/bash に Full Disk Access 付与済みなので、bash を入口にする。
#   [[reference_launchd_cloudstorage_fda]]
# パスワードはキーチェーン（security find-generic-password）から読む。
# パスワード未設定のアカウント（iCloud/Google 等）は sync.py 側で自動スキップされる。
cd "$(dirname "$0")" || exit 1

LOG="local/sync-daily.log"
mkdir -p local

if [ ! -x .venv/bin/python3 ]; then
  echo "$(date '+%Y-%m-%d %H:%M:%S') .venv が無い。run.sh を一度実行して作成すること" >> "$LOG"
  exit 1
fi

echo "===== $(date '+%Y-%m-%d %H:%M:%S') 自動取り込み開始 =====" >> "$LOG"
.venv/bin/python3 sync.py --all-accounts --sync >> "$LOG" 2>&1
rc=$?

# --- 新しく入った英語メールを日本語に訳す（2026-08-27 追加）---
# なぜ要るか: 埋め込みは多言語対応だが、**日本語で聞くと日本語メールが上位を占め**、
#   英文メールは5万通の中に埋もれて上位800にすら入らない（実測）。
#   日本語の要約を持たせて**訳文でベクトルを作る**と順位が跳ね上がり、
#   全文検索でも日本語の語で英文メールが引っかかるようになる。
#   ★ここを飛ばすと、その日に届いた英語メールだけ日本語で探せない状態になる。
echo "----- $(date '+%Y-%m-%d %H:%M:%S') 英語メールの日本語訳（新着分） -----" >> "$LOG"
/usr/bin/python3 translate_english.py >> "$LOG" 2>&1

# --- 新着ぶんの意味検索ベクトルを作る（無い分だけ・.venv-embed で実行）---
# 重い torch は閲覧UIに載せず、この専用venvだけが持つ。初回は全件で時間がかかるが、
# 以後は毎日の新着ぶんだけなので数十秒で終わる。
if [ -x .venv-embed/bin/python ]; then
  echo "----- $(date '+%Y-%m-%d %H:%M:%S') 意味検索ベクトルの追加 -----" >> "$LOG"
  .venv-embed/bin/python embed_backfill.py >> "$LOG" 2>&1
  # 訳が付いたものは**訳文で**ベクトルを作り直す（原文のベクトルのままだと日本語で引けない）
  .venv-embed/bin/python embed_backfill.py --retranslated >> "$LOG" 2>&1
fi

# --- 保存期間の適用（メール日付が1年より前をサーバーから削除）---
# ★戻せない操作。オーナーの明示指示で自動化（2026-08-26）。
#   ・判定は「メール日付が365日より前」だけ（取り込みからの据置日数は使わない）
#   ・各アカウントの .env に ARCHIVE_DELETE_ENABLED=1 / ARCHIVE_RETENTION_DAYS=365 がある物だけ実際に消える
#   ・送信/下書き/ゴミ箱の扱いは各 .env の ARCHIVE_EXCLUDE_FOLDERS に従う
#   ・削除前に1通ずつ SHA/Message-ID/UIDVALIDITY を再確認し、通らない物は飛ばす（sync.py 側）
#   ・--all-accounts と --delete は併用できないので、アカウントごとに回す
echo "----- $(date '+%Y-%m-%d %H:%M:%S') 保存期間の適用（1年超を削除） -----" >> "$LOG"
for f in .env.mail-archiver.*; do
  case "$f" in
    *.example) continue ;;
  esac
  slug="${f#.env.mail-archiver.}"
  .venv/bin/python3 sync.py --account "$slug" --delete --yes \
      --older-than-days 365 --max-delete 100000 >> "$LOG" 2>&1
done

echo "----- $(date '+%Y-%m-%d %H:%M:%S') 終了 sync_rc=$rc -----" >> "$LOG"
exit $rc
