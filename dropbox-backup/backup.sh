#!/bin/bash
# 社内共有フォルダ → 個人Dropbox へ週1回ミラーする。
#
#   元: 大京商事Dropbox / 共有フォルダ / （★必読★）新共有フォルダ   （社員が全員触る）
#   先: 個人Dropbox / 社内バックアップ / （★必読★）新共有フォルダ   （オーナーしか触らない）
#
# 方式はミラー（rsync -a --delete）。元で消えたファイルは次回の実行で先からも消える。
# ただし1回で MAX_DELETE 件以上消える回は、1件も触らずに中断して人に知らせる。
#
# ★ launchd から動かすので Dropbox(CloudStorage) の TCC に注意。
#   plist は必ず /bin/bash 経由で呼ぶこと（/bin/bash にフルディスクアクセスが要る）。
# ★ macOS の /usr/bin/rsync は openrsync で、GNU rsync とは挙動が違う。
#   --backup を付けると --delete が効かなくなる（＝ミラーにならない）ので使わない。実測済み。

set -u
set -o pipefail

# ★ launchd から起動されると PATH もロケールも空になる。両方ここで明示する。
#   ロケールが C のままだと bash が全角文字を変数名の一部として読んでしまい、
#   "$VAR）" が「VAR）という未定義変数」になって set -u で落ちる（2026-08-31に実際に踏んだ）。
#   その保険として、このスクリプトでは変数を必ず ${VAR} と波括弧で書く。
export PATH="/usr/bin:/bin:/usr/sbin:/sbin"
export LANG="ja_JP.UTF-8"
export LC_ALL="ja_JP.UTF-8"

SRC="/Users/apple/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ"
DST_ROOT="/Users/apple/Library/CloudStorage/Dropbox-個人/CLAUDE/社内バックアップ"
DST="${DST_ROOT}/（★必読★）新共有フォルダ"

BASE="/Users/apple/dropbox-backup"
LOG_DIR="${BASE}/logs"
LOCK="${BASE}/.lock"
STATUS="${BASE}/last-run.txt"

# 安全弁 --------------------------------------------------------------------
# Dropbox が同期していない・アンマウントされている状態で走らせると、元が空に見えて
# --delete がバックアップを消し飛ばす。それを防ぐための下限。
MIN_FILES=15000

# 1回で MAX_DELETE 件以上消える変更は、事故を疑って中断する（オーナー指示: 50件）。
# 社内の整理でフォルダ1つ移しただけでも超えるので、超えたら通知を出して人が見る。
# 中身を確認して「これは正しい削除」と判断したら、上限を上げて手で流す:
#     MAX_DELETE=99999 bash /Users/apple/dropbox-backup/backup.sh
MAX_DELETE="${MAX_DELETE:-50}"

RSYNC=/usr/bin/rsync

# ★--inplace が要る理由（2026-08-31 実測）
#   openrsync は転送中 ".<元の名前>.XXXXXXXX" という一時ファイルを作る。元の名前が長いと
#   この一時名が 255 バイトを超え、**UTF-8の途中で切られて** mkstempat が
#   「Illegal byte sequence」で失敗し、rsync ごと落ちる（19,050件でエラー終了した）。
#   実際に該当したのは 299 バイトの PDF など2件。--inplace は一時ファイルを作らないので通る。
#   代償: 転送が途中で切れると転送先のファイルが半端な状態で残る。ただし mtime が
#   合わなくなるので、次回の実行で必ず転送し直される。
INPLACE=--inplace

EXCLUDES=(
  --exclude=.DS_Store
  --exclude=.dropbox
  --exclude=.dropbox.attr
  --exclude=.dropbox.cache/
  --exclude=.TemporaryItems/
  --exclude='Icon?'
)

TS="$(date '+%Y-%m-%d %H:%M:%S')"
STAMP="$(date '+%Y%m%d-%H%M%S')"
LOG="${LOG_DIR}/backup-${STAMP}.log"
PLAN="${LOG_DIR}/.plan-${STAMP}.txt"

mkdir -p "${LOG_DIR}"

log() { printf '%s  %s\n' "$(date '+%H:%M:%S')" "$*" | tee -a "${LOG}"; }

# openrsync は日本語ファイル名の一部のバイトを "\#NNN"（8進）へ逃がして出力する。
# そのままでは人が読めず、「何が消えるのか確認する」という安全弁の意味が無くなるので戻す。
decode_names() {
  /usr/bin/python3 -c '
import re,sys
data = sys.stdin.buffer.read()
data = re.sub(rb"\\#([0-7]{3})", lambda m: bytes([int(m.group(1), 8)]), data)
sys.stdout.buffer.write(data)
' 2>/dev/null || cat
}

# 画面が無い時間帯に走るので、止まったことに気づけるよう通知を出す。
# launchd から osascript が通らない環境もあるので失敗は無視する。
notify() {
  /usr/bin/osascript -e "display notification \"$1\" with title \"社内共有フォルダのバックアップ\"" \
    >/dev/null 2>&1 || true
}

finish() {
  local code="$1" msg="$2"
  printf '%s\n' "${TS}  ${msg}" > "${STATUS}"
  log "${msg}"
  [ "${code}" -ne 0 ] && notify "${msg}"
  rm -f "${PLAN}"
  rmdir "${LOCK}" 2>/dev/null
  # ログは12週ぶんだけ残す
  ls -1t "${LOG_DIR}"/backup-*.log 2>/dev/null | tail -n +13 | while read -r f; do rm -f "${f}"; done
  exit "${code}"
}

# 二重起動の防止（mkdir は原子的。macOS に flock は無い）
if ! mkdir "${LOCK}" 2>/dev/null; then
  log "NG: 前回の実行がまだ動いている。中止 -> ${LOCK}"
  exit 1
fi
trap 'rmdir "${LOCK}" 2>/dev/null' EXIT

log "=== 社内共有フォルダのバックアップ 開始 ==="
log "元: ${SRC}"
log "先: ${DST}"
log "削除の上限: ${MAX_DELETE} 件"

# 1. 元がちゃんと見えているか -------------------------------------------------
if [ ! -d "${SRC}" ]; then
  finish 1 "NG: 元フォルダが見えない。Dropbox未同期／TCC未許可の疑い。何もせず中止"
fi

SRC_FILES=$(find "${SRC}" -type f 2>/dev/null | wc -l | tr -d ' ')
log "元のファイル数: ${SRC_FILES} 件"
if [ "${SRC_FILES}" -lt "${MIN_FILES}" ]; then
  finish 1 "NG: 元が ${SRC_FILES} 件しかない（下限 ${MIN_FILES}）。同期途中の疑い。何もせず中止"
fi

# 2. 先の置き場を用意 --------------------------------------------------------
if [ ! -d "${DST_ROOT}" ]; then
  finish 1 "NG: 保存先が見えない -> ${DST_ROOT}"
fi
mkdir -p "${DST}" || finish 1 "NG: 保存先を作れなかった -> ${DST}"

# 3. 先に空実行して、何件消えるかを数える ------------------------------------
# --max-delete だけでは「上限まで消してから止まる」ので、消される前に数える。
log "空実行で削除件数を確認中..."
"${RSYNC}" -a -n "${INPLACE}" --delete "${EXCLUDES[@]}" --itemize-changes "${SRC}/" "${DST}/" > "${PLAN}" 2>&1
PLAN_RC=$?
if [ "${PLAN_RC}" -ne 0 ]; then
  finish "${PLAN_RC}" "NG: 空実行が終了コード ${PLAN_RC} で失敗。ログ -> ${LOG}"
fi

WILL_DELETE=$(grep -a -c '^\*deleting' "${PLAN}" || true)
WILL_DELETE=${WILL_DELETE:-0}
log "このまま実行すると ${WILL_DELETE} 件が削除される"

if [ "${WILL_DELETE}" -gt "${MAX_DELETE}" ]; then
  # 何が消えるのかをログに残す（最大200件）。人が見て判断するための材料。
  log "--- 削除予定（先頭200件） ---"
  grep -a '^\*deleting' "${PLAN}" | head -200 | decode_names >> "${LOG}"
  finish 1 "中断: ${WILL_DELETE} 件が消える予定（上限 ${MAX_DELETE}）。バックアップは触っていない。ログを確認 -> ${LOG}"
fi

# 4. 本番のミラー ------------------------------------------------------------
log "rsync 開始（ミラー）"
"${RSYNC}" -a "${INPLACE}" --delete --max-delete="${MAX_DELETE}" "${EXCLUDES[@]}" --itemize-changes \
  "${SRC}/" "${DST}/" >> "${LOG}" 2>&1
RC=$?

# 5. 結果 --------------------------------------------------------------------
ADDED=$(grep -a -c '^>f+++++++' "${LOG}" || true)
UPDATED=$(grep -a -cE '^>f[^+]' "${LOG}" || true)
DELETED=$(grep -a -c '^\*deleting' "${LOG}" || true)
DST_FILES=$(find "${DST}" -type f 2>/dev/null | wc -l | tr -d ' ')
SIZE=$(du -sh "${DST}" 2>/dev/null | cut -f1)

ERRORS=$(grep -a -c 'error:' "${LOG}" || true)
ERRORS=${ERRORS:-0}

log "追加 ${ADDED:-0} / 更新 ${UPDATED:-0} / 削除 ${DELETED:-0}"
log "バックアップ後: ${DST_FILES} 件 / ${SIZE}"

if [ "${RC}" -ne 0 ]; then
  finish "${RC}" "NG: rsync が終了コード ${RC} で失敗。ログ -> ${LOG}"
fi

# 終了コード0でも個別のファイルで失敗していることがあるので、error: 行も見る
if [ "${ERRORS}" -gt 0 ]; then
  finish 1 "NG: ${ERRORS} 件のファイルでエラー。ログの error: 行を確認 -> ${LOG}"
fi

# 元と先の件数が合っているかで最終確認（除外は .DS_Store 等だけなので、ほぼ一致するはず）
if [ "${DST_FILES}" -lt $(( SRC_FILES - SRC_FILES / 20 )) ]; then
  finish 1 "NG: 元 ${SRC_FILES} 件に対し先が ${DST_FILES} 件しかない。ログ -> ${LOG}"
fi

finish 0 "OK: ${DST_FILES} 件 / ${SIZE} 「追加 ${ADDED:-0} 更新 ${UPDATED:-0} 削除 ${DELETED:-0}」"
