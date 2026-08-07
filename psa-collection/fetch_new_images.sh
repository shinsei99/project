#!/bin/bash
# 新規カードの画像を取得する。app.collectors.com にログイン済みSafariで実行。
# harvest_collectors.js で画像URLを集め、import_from_web.py で未取得分だけDLする。
set -e
cd "$(dirname "$0")"
JS_FILE="$(pwd)/harvest_collectors.js"
JSONL="$(pwd)/data/_harvest_items.jsonl"
PY="$(pwd)/.venv/bin/python3"
[ -x "$PY" ] || PY="python3"

echo "▶ Safari で app.collectors.com を開いています…"
open -a Safari "https://app.collectors.com/collection/"
sleep 4

URL=$(osascript -e 'tell application "Safari" to return URL of document 1' 2>/dev/null || echo "")
case "$URL" in
  *collectors.com*) : ;;
  *) echo "✗ collectors.com が前面にありません（URL=$URL）。ログインして開いてから再実行してください。"; exit 1 ;;
esac
if echo "$URL" | grep -qi "signin\|login"; then
  echo "✗ 未ログインです（$URL）。ログインしてから再実行してください。"; exit 1
fi

echo "▶ 画像URLを収集中（全ACTIVEをページング）…"
# 前回実行の残骸(__h)を消してから流し込む（古いdone状態の空読み防止）
osascript -e 'tell application "Safari" to do JavaScript "delete window.__h; 1" in document 1' >/dev/null 2>&1
osascript >/dev/null <<OSA
set js to (read POSIX file "$JS_FILE" as «class utf8»)
tell application "Safari" to do JavaScript js in document 1
OSA

for i in $(seq 1 40); do
  DONE=$(osascript -e 'tell application "Safari" to do JavaScript "(window.__h&&window.__h.done)?(window.__h.error?(\"ERR \"+window.__h.error):\"ok\"):\"wait\"" in document 1' 2>/dev/null || echo "wait")
  case "$DONE" in
    ok) break ;;
    ERR*) echo "✗ 収集エラー: $DONE"; exit 1 ;;
    *) sleep 1 ;;
  esac
done

# __h.items を1行1JSONのJSONLで書き出す
osascript -e 'tell application "Safari" to do JavaScript "window.__h.items.map(function(x){return JSON.stringify(x)}).join(\"\n\")" in document 1' > "$JSONL" 2>/dev/null

LINES=$(wc -l < "$JSONL" | tr -d ' ')
echo "▶ 収集 $LINES 件。未取得分をダウンロードします…"
"$PY" import_from_web.py "$JSONL"
rm -f "$JSONL"
