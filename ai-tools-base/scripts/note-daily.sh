#!/bin/bash
# note へ1日1本、まだ出していない原稿を投稿する（launchd から毎晩叩く）。
#
#   ./scripts/note-daily.sh            1本投稿する
#   ./scripts/note-daily.sh --dry      下書きまでで止める（試すとき）
#
# 順番は drafts/zenn_order.txt。出したものは drafts/.note_posted.json に残るので、
# 二重投稿しない。ログイン用のプロファイルは ~/.note-profile（初回だけ --login が要る）。
set -u

# ★launchd から起動されると PATH が空になり、claude CLI の終了フック（Vercelプラグインの
#   session-end-cleanup.mjs）が呼ぶ node が見つからず、**claude が毎回エラー終了する**。
#   2026-08-28未明のOCR全滅・翻訳940通全滅はこれが原因だった（定額枠切れではない）。
#   手で流すと PATH があるので再現しない＝気づきにくい。[[reference_launchd_path_node]]
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")/.."

# Python は Visual Agent と同じ探し方（特定アプリの .venv に依存しない）
PY="${VA_PYTHON:-}"
for cand in "$HOME/agent-platform/.venv/bin/python" "$HOME/.va-venv/bin/python" "$(command -v python3)"; do
  [ -z "$PY" ] && [ -x "$cand" ] && PY="$cand"
done

echo "=== $(date '+%Y-%m-%d %H:%M') note-daily ==="

# ★静止期間（2026-09-03）。drafts/note_quiet_until.txt に書いた日時までは**投稿しない**。
#   なぜ要るか: note 側の関門（note_post.py の _zenn_live）は「Zennに出ていない記事を
#   noteが追い越さない」ためのもので、**通算本数を合わせる働きは無い**。
#   8/27 のZennデプロイ停止事故でズレた1本ぶん（Zenn 12 / note 13）は、
#   Zennが動き出すと差が付いたまま並走してしまう。差を詰めるには
#   **noteだけを1晩見送る**しかなく、その1晩を作るのがこのファイル。
#   ★launchd を外す形にはしない。外すと戻し忘れて永久に止まる（zenn-daily と同じ設計）。
#     日時を過ぎれば**勝手に復帰する**。前倒しで再開したいならファイルを消すだけ。
QUIET="drafts/note_quiet_until.txt"
if [ -f "$QUIET" ]; then
  UNTIL="$(grep -v '^#' "$QUIET" | head -1 | tr -d ' \t')"
  NOW="$(date '+%Y-%m-%dT%H:%M')"
  if [ -n "$UNTIL" ] && [ "$NOW" \< "$UNTIL" ]; then   # ISO表記なので文字列比較で正しく並ぶ
    echo "静止期間中（$UNTIL まで）。今夜は投稿しない。"
    echo "  理由: $(grep '^#' "$QUIET" | head -2 | tr '\n' ' ')"
    exit 0
  fi
  # ${} 必須: 直後が全角括弧だと bash が変数名に巻き込む（run_ocr_nightly.sh と同じ罠）
  echo "静止期間（${UNTIL}）を過ぎたので再開する。"
fi

"$PY" scripts/note_post.py --check || { echo "ログインが切れている。--login をやり直すこと"; exit 1; }
"$PY" scripts/note_post.py --next "$@"
