#!/bin/bash
# spacemarket-monitor の入口。
#
#   ./run.sh public    公開ページから3施設の現状を取る（ログイン不要・すぐ動く）
#   ./run.sh login     ホスト管理画面に人が1回だけ手動ログインする（Chromeが開く）
#   ./run.sh dump      ログイン済みセッションで管理画面の中身を丸ごと取得する（初回の調査用）
#   ./run.sh host      ホスト管理画面の実績レポートを作る（REST APIを直接叩く・普段はこれ）
#
# Python は Playwright が入っているものを探す。特定アプリの .venv に依存しないよう、
# CLAUDE.md の共通Visual Agentと同じ順番（VA_PYTHON → agent-platform → .va-venv → python3）。
set -euo pipefail
cd "$(dirname "$0")"

pick_python() {
  for p in "${VA_PYTHON:-}" "$HOME/agent-platform/.venv/bin/python" "$HOME/.va-venv/bin/python"; do
    [ -n "$p" ] && [ -x "$p" ] && "$p" -c "import playwright" 2>/dev/null && { echo "$p"; return; }
  done
  # 公開ページ側（public）は Playwright 不要なので、無ければ素の python3 で足りる
  command -v python3
}

PY="$(pick_python)"
CMD="${1:-public}"

case "$CMD" in
  public) exec "$PY" public_check.py ;;
  login)  exec "$PY" login.py ;;
  dump)   exec "$PY" host_dump.py ;;
  host)   exec "$PY" host_check.py ;;
  *) echo "使い方: ./run.sh [public|login|host|dump]" >&2; exit 2 ;;
esac
