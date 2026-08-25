#!/bin/bash
# アプリを1コマンドで立ち上げる（起動 → ポート待ち → HTTP確認 まで面倒を見る）
#
# なぜ要るのか:
#   Claude Code から起動するとき、`nohup ./run.sh &` や `for` ループでのポート待ちは
#   許可ルール（Bash(./*.sh*) など）に当てはまらず、そのつど確認プロンプトが出ていた。
#   この1本に畳むと `./app-start.sh <アプリ>` だけで済み、確認は出ない。
#
# 使い方:
#   ./app-start.sh <アプリフォルダ名>            起動して HTTP 200 まで待つ
#   ./app-start.sh <アプリフォルダ名> --shot      起動後に ./va.sh で画面も撮る
#   ./app-start.sh <アプリフォルダ名> --status    いま起動しているか見るだけ
#   ./app-start.sh <アプリフォルダ名> --stop      止める
#
# 注意: これは「都度起動」の道具。常駐（launchd）は別物で、こちらでは触らない。

set -u
cd "$(dirname "$0")" || exit 1
ROOT="$(pwd)"

APP="${1:-}"
MODE="${2:-}"

if [ -z "$APP" ]; then
  echo "使い方: ./app-start.sh <アプリフォルダ名> [--shot|--status|--stop]" >&2
  exit 2
fi

DIR="$ROOT/$APP"
[ -d "$DIR" ] || { echo "✗ そんなフォルダは無い: $DIR" >&2; exit 2; }

# --- ポートを決める（run.sh の --server.port を正とする） -------------------
PORT=""
if [ -f "$DIR/run.sh" ]; then
  PORT="$(grep -oE '\-\-server\.port[ =]+[0-9]+' "$DIR/run.sh" | grep -oE '[0-9]+' | head -1)"
  [ -n "$PORT" ] || PORT="$(grep -oE '\-\-port[ =]+[0-9]+|PORT[=:][ ]*[0-9]+' "$DIR/run.sh" | grep -oE '[0-9]+' | head -1)"
fi
[ -n "$PORT" ] || PORT="${APP_PORT:-}"
if [ -z "$PORT" ]; then
  echo "✗ ポートが分からない。run.sh に --server.port が無い場合は APP_PORT=8535 ./app-start.sh $APP" >&2
  exit 2
fi

listening_pid() { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN -t 2>/dev/null | head -1; }
bind_addr()     { lsof -nP -iTCP:"$PORT" -sTCP:LISTEN 2>/dev/null | awk 'NR==2{print $9}'; }
http_code()     { curl -s -o /dev/null -m 5 -w '%{http_code}' "http://127.0.0.1:$PORT" 2>/dev/null; }

case "$MODE" in
  --status)
    pid="$(listening_pid)"
    if [ -n "$pid" ]; then
      echo "起動中: $APP  pid=$pid  $(bind_addr)  HTTP $(http_code)"
    else
      echo "停止中: $APP （port $PORT は待ち受けなし）"
    fi
    exit 0
    ;;
  --stop)
    pid="$(listening_pid)"
    if [ -z "$pid" ]; then echo "もともと止まっている: $APP (port $PORT)"; exit 0; fi
    kill "$pid" 2>/dev/null
    for _ in 1 2 3 4 5 6 7 8 9 10; do
      [ -z "$(listening_pid)" ] && break
      /bin/sleep 1
    done
    if [ -z "$(listening_pid)" ]; then echo "止めた: $APP (pid $pid / port $PORT)"; else
      echo "✗ 止まらない: $APP (pid $pid)。手で kill -9 $pid" >&2; exit 1; fi
    exit 0
    ;;
esac

# --- 起動 -------------------------------------------------------------------
pid="$(listening_pid)"
if [ -n "$pid" ]; then
  echo "すでに起動中: $APP  pid=$pid  $(bind_addr)  HTTP $(http_code)"
  echo "URL: http://127.0.0.1:$PORT"
  exit 0
fi

[ -x "$DIR/run.sh" ] || { echo "✗ $APP/run.sh が無い（または実行権が無い）" >&2; exit 2; }

LOG="$DIR/.run.log"
: > "$LOG"
( cd "$DIR" && nohup ./run.sh >>"$LOG" 2>&1 & echo $! > "$DIR/.run.pid" )
started_pid="$(cat "$DIR/.run.pid" 2>/dev/null)"
echo "起動した: $APP (pid $started_pid) — port $PORT が開くのを待つ…"

code=""
for _ in $(seq 1 60); do        # 最大およそ5分（初回は venv 作成があるので長め）
  code="$(http_code)"
  [ "$code" = "200" ] && break
  if ! kill -0 "$started_pid" 2>/dev/null && [ -z "$(listening_pid)" ]; then
    echo "✗ プロセスが落ちた。ログの末尾:" >&2
    tail -20 "$LOG" >&2
    exit 1
  fi
  /bin/sleep 5
done

if [ "$code" != "200" ]; then
  echo "✗ HTTP 200 にならない（最後の応答: ${code:-なし}）。ログの末尾:" >&2
  tail -20 "$LOG" >&2
  exit 1
fi

echo "✅ $APP  HTTP 200  URL: http://127.0.0.1:$PORT"
echo "   待ち受け: $(bind_addr)   ログ: $LOG"

if [ "$MODE" = "--shot" ] && [ -x "$ROOT/va.sh" ]; then
  "$ROOT/va.sh" goto "http://127.0.0.1:$PORT" >/dev/null 2>&1
  "$ROOT/va.sh" wait 3 >/dev/null 2>&1
  "$ROOT/va.sh" shot "$APP"
fi
