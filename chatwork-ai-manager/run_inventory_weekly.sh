#!/bin/bash
# 棚卸しExcel「全ファイル一覧.xlsx」を作り直して、共有フォルダの実物を置き換える。
# launchd から週1回（日曜 5:00）。
#
# ★2026-09-03: file-finder（横断ファイル検索・8520）から移設した。
#   アプリ本体は廃止したが、この棚卸しだけは残す。作られるExcelは
#     1. AI業務マネージャーの知識索引（毎晩の refresh が拾う）
#     2. find_files ツールの元データ
#     3. **全社員が共有フォルダで直接開いている実物**
#   の3役を兼ねているため。以前あった「8520 を kickstart して HTTP 200 を待つ」
#   工程は、読み手のアプリが無くなったので外した。
#   索引への反映は AI業務マネージャーの定時 refresh に任せる（ここでは呼ばない。
#   日曜5:00 に索引を走らせると、22:00 の通常の refresh と二重になる）。
#
# ★なぜ bash 経由なのか（plist から python を直接叩かない）
#   Dropbox（CloudStorage）は launchd の常駐からは TCC で読めない。
#   ただし **/bin/bash にフルディスクアクセスがあれば読める**（TCCの責任プロセスが bash になるため）。
#   plist から /usr/bin/python3 を直接叩くと責任プロセスが python になり、また読めなくなる。
#   → 必ずこのスクリプトを経由させること。
#
# ★なぜ PATH を明示するのか
#   launchd から起動されると PATH が空になる（2026-08-28 に別ジョブで実際に踏んだ）。
#
# 手で流すとき:
#   ./run_inventory_weekly.sh          # 本番と同じ（共有フォルダも置き換える）
#   DRY=1 ./run_inventory_weekly.sh    # 下見だけ（共有フォルダは触らない）
set -u
# ★${} を省略しない。直後が全角括弧だと bash が変数名に巻き込む（$rc） → 変数 rc）扱い。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")" || exit 1

LOG="$HOME/Library/Logs/com.shinsei.chatwork-ai-manager-inventory.log"
log() { echo "[$(date '+%F %T')] $*" | tee -a "$LOG"; }

log "=== 棚卸しの作り直し 開始 ==="

if [ -n "${DRY:-}" ]; then
  /usr/bin/python3 build_inventory.py >>"$LOG" 2>&1
  rc=$?
  log "下見のみ（終了コード ${rc}）。共有フォルダは触っていない"
  exit "$rc"
fi

/usr/bin/python3 build_inventory.py --publish >>"$LOG" 2>&1
rc=$?
if [ "$rc" -ne 0 ]; then
  log "★作り直しに失敗（終了コード ${rc}）。共有フォルダは置き換えていない（古いままの方が安全）"
  exit "$rc"
fi

# ★控えの世代管理。アーカイブに毎週1本たまるので、8本（約2か月）を超えたら古いものから消す。
#   消す前に件数を出す（黙って消さない）。
ARC="$HOME/Library/CloudStorage/Dropbox-大京商事　株式会社/共有フォルダ/（★必読★）新共有フォルダ/_アーカイブ（2027年7月削除予定）"
KEEP=8
if [ -d "$ARC" ]; then
  n=$(ls -1 "$ARC"/全ファイル一覧_*_旧.xlsx 2>/dev/null | wc -l | tr -d ' ')
  if [ "$n" -gt "$KEEP" ]; then
    log "控えが $n 本ある。古い $((n - KEEP)) 本を消す（$KEEP 本＝約2か月分を残す）"
    ls -1 "$ARC"/全ファイル一覧_*_旧.xlsx | sort | head -n "$((n - KEEP))" | while read -r f; do
      log "  消す: $(basename "$f")"
      rm -f "$f"
    done
  else
    log "控えは $n 本（$KEEP 本まで残す）"
  fi
fi

log "=== 終了 ==="
exit 0
