#!/bin/bash
# 夜間のOCR一括取込（launchd から毎晩1回・02:00開始／2時間で打ち切り）。
#
# なぜ bash 経由なのか:
#   Dropbox（CloudStorage）は launchd の常駐からは TCC で読めない。
#   ただし **/bin/bash にフルディスクアクセスがあれば読める**（TCCの責任プロセスが bash になるため）。
#   plist から /usr/bin/python3 を直接叩くと責任プロセスが python になり、また読めなくなる。
#   → 必ずこのスクリプトを経由させること。[[reference_launchd_cloudstorage_fda]]
#
# なぜ --max-new なのか:
#   --limit は「対象リストの先頭N件」を切り出すだけで、毎晩流すと同じ先頭を舐めて終わる。
#   --max-new は取込済みを飛ばしながら進み、**新しく処理できた件数**で止まる。
#
# 手で流すとき:
#   ./run_ocr_nightly.sh                  # 既定（300件 / 120分）
#   OCR_MAX_NEW=20 ./run_ocr_nightly.sh
#   OCR_MAX_MINUTES=60 ./run_ocr_nightly.sh
set -u

# ★launchd から起動されると PATH が空になり、claude CLI の終了フック（Vercelプラグインの
#   session-end-cleanup.mjs）が呼ぶ node が見つからず、**claude が毎回エラー終了する**。
#   2026-08-28未明のOCR全滅・翻訳940通全滅はこれが原因だった（定額枠切れではない）。
#   手で流すと PATH があるので再現しない＝気づきにくい。[[reference_launchd_path_node]]
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
set -m          # 子を独立したプロセスグループにする（下の cleanup でまとめて止めるため）
cd "$(dirname "$0")" || exit 1

# ★1晩1,000件（2026-09-04 オーナー指示）。300件では9月半ばまでかかるため。
#   上げてよいと判断した根拠（9/4未明の実測）: 300件に **7.7分** で到達した＝持ち時間120分の
#   6%しか使っていない。時間ではなく件数の上限で止まっていたので、上げれば素直に速くなる。
#   残り約3,300件 → 3〜4晩で終わる見込み。**枠を食う工程なので、終わったら300へ戻してよい。**
MAX_NEW="${OCR_MAX_NEW:-1000}"
MAX_MIN="${OCR_MAX_MINUTES:-120}"     # 02:00 開始で 04:00 に終わる（2026-08-28 オーナー指定）
# ★2並列（2026-09-02 オーナー指示）。残り約3,900件を直列（実測186件/晩）で片付けると
#   25晩以上かかるため。上げすぎない理由: claude の呼び出しが同時に増える＝定額枠を
#   その分だけ速く食う。SQLite の書き込みがぶつかる回数も増える（ログの「DBロック」で見る）。
WORKERS="${OCR_WORKERS:-2}"
LOG="$HOME/Library/Logs/com.shinsei.chatwork-ai-manager-ocr.log"
LOCK="/tmp/chatwork-ocr-nightly.lock"
CHILD=""

# launchd の StandardOutPath も同じ $LOG を指しているので、
# 標準出力にも書くと**同じ行が2回入る**。画面で見えるのは手で流したときだけでよい。
log() {
  local m="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
  if [ -t 1 ]; then echo "$m" | tee -a "$LOG"; else echo "$m" >> "$LOG"; fi
}

# 後始末。★子ごと止めること:
#   caffeinate は python を子に持つので、caffeinate だけ kill しても python が生き残る。
#   実際 launchctl bootout / kill では python が孤児として走り続けた（2026-08-27 実測）。
#   set -m でプロセスグループを分けてあるので、-$CHILD でまとめて倒す。
cleanup() {
  if [ -n "$CHILD" ]; then kill -TERM "-$CHILD" 2>/dev/null; fi
  rm -rf "$LOCK"
}
trap cleanup EXIT INT TERM

# --- 多重起動を防ぐ（前の晩の分がまだ走っていることがある） -------------------
# mkdir は原子的なのでロックに使える。中に PID を置き、死んでいたら奪う。
if ! mkdir "$LOCK" 2>/dev/null; then
  OLD="$(cat "$LOCK/pid" 2>/dev/null)"
  if [ -n "$OLD" ] && kill -0 "$OLD" 2>/dev/null; then
    log "先行ジョブ(PID $OLD)が実行中のため今回は見送る"
    trap - EXIT; exit 0            # 人のロックを消さない
  fi
  log "古いロックを掃除して続行（PID ${OLD:-不明} は不在）"
  rm -rf "$LOCK"; mkdir "$LOCK" 2>/dev/null || { log "ロックを取れなかった"; trap - EXIT; exit 1; }
fi
echo $$ > "$LOCK/pid"

log "OCR夜間ジョブ開始（最大 ${MAX_NEW}件 / ${MAX_MIN}分 / ${WORKERS}並列）"

# caffeinate: 長時間ジョブの途中でスリープに入られると中断されるため
# （このMacは普段スリープしない設定だが、ジョブ側でも保険をかけておく）
/usr/bin/caffeinate -i /usr/bin/python3 ocr_ingest.py \
  --max-new "$MAX_NEW" --max-minutes "$MAX_MIN" --workers "$WORKERS" >> "$LOG" 2>&1 &
CHILD=$!
wait "$CHILD"
rc=$?
CHILD=""       # 正常終了したので cleanup で kill しない

log "OCR夜間ジョブ終了（終了コード ${rc}）"   # ${} 必須: 直後が全角括弧だと bash が変数名に巻き込む
exit "$rc"
