#!/bin/bash

# ★launchd から起動されると PATH が空になり、claude CLI の終了フック（Vercelプラグインの
#   session-end-cleanup.mjs）が呼ぶ node が見つからず、**claude が毎回エラー終了する**。
#   2026-08-28未明のOCR全滅・翻訳940通全滅はこれが原因だった（定額枠切れではない）。
#   手で流すと PATH があるので再現しない＝気づきにくい。[[reference_launchd_path_node]]
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
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
# 1晩100通まで（既定・2026-08-28 オーナー指定）。実測1バッチ5通=45秒なので約15分。
# 取込8分と合わせて00:30開始→01:00までに終わる想定。02:00のOCRと枠を取り合わない。
/usr/bin/python3 translate_english.py --limit "${TRANSLATE_MAX:-100}" >> "$LOG" 2>&1

# --- 添付の中身を索引に入れる（2026-08-31 追加・小分け）---
# なぜ要るか: 添付はこれまで「保管してダウンロードできる」だけで**中身は検索できなかった**。
#   実例: PTA大会の会場「スイスホテル南海大阪」はメール本文に一度も出てこず、
#   スキャンPDFの中にしかない。どんな語で検索しても当たらなかった（2026-08-31 実測）。
#
# ★1晩あたりの上限を付けて少しずつ進める（39,726件を一気にやらない）。
#   `--max-minutes` で切り、途中で終わっても**1添付1行**を必ず書いているので翌晩は続きから。
# ★OCR は macOS Vision（`tools/ocr_pdf`）＝**claude の定額枠を使わない**ので、
#   02:00 からの AI業務マネージャーのOCR夜間ジョブと取り合わない（実測 2.3秒/ページ）。
# ★/usr/bin/python3 で呼ぶ（pdfplumber/openpyxl/python-docx/xlrd はそちらに入っている。
#   .venv には無い）。translate_english.py と同じ流儀。
#
# ★2段に分ける（2026-08-31 オーナー指示「常に全体のメールを文字で把握できる状態へ」）。
#   ① その晩に届いた新着＝**必ず当夜に片付ける**（上限を付けない。数十件なので数分）
#   ② 過去の積み残し＝時間で小分け（初回は約4万件あるので何晩かに分かれる）
#   分けないと、積み残しの山を処理している最中に時間切れになり、
#   **その日届いたメールの添付だけ永久に後回し**になる（新着は毎日増えるため）。
echo "----- $(date '+%Y-%m-%d %H:%M:%S') 添付の中身（① 新着ぶん） -----" >> "$LOG"
/usr/bin/python3 attach_extract.py --since-days "${ATTACH_NEW_DAYS:-30}" \
    --workers "${ATTACH_WORKERS:-4}" >> "$LOG" 2>&1

echo "----- $(date '+%Y-%m-%d %H:%M:%S') 添付の中身（② 積み残し・小分け） -----" >> "$LOG"
/usr/bin/python3 attach_extract.py --max-minutes "${ATTACH_MAX_MIN:-45}" \
    --workers "${ATTACH_WORKERS:-4}" >> "$LOG" 2>&1

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
