#!/bin/bash
# note へ1日1本、まだ出していない原稿を投稿する（launchd から毎晩叩く）。
#
#   ./scripts/note-daily.sh            1本投稿する
#   ./scripts/note-daily.sh --dry      下書きまでで止める（試すとき）
#
# 順番は drafts/zenn_order.txt。出したものは drafts/.note_posted.json に残るので、
# 二重投稿しない。ログイン用のプロファイルは ~/.note-profile（初回だけ --login が要る）。
set -u
cd "$(dirname "$0")/.."

# Python は Visual Agent と同じ探し方（特定アプリの .venv に依存しない）
PY="${VA_PYTHON:-}"
for cand in "$HOME/agent-platform/.venv/bin/python" "$HOME/.va-venv/bin/python" "$(command -v python3)"; do
  [ -z "$PY" ] && [ -x "$cand" ] && PY="$cand"
done

echo "=== $(date '+%Y-%m-%d %H:%M') note-daily ==="
"$PY" scripts/note_post.py --check || { echo "ログインが切れている。--login をやり直すこと"; exit 1; }
"$PY" scripts/note_post.py --next "$@"
