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

echo "▶ 画像URLを収集中（保有中＋売却済を全ページング）…"
# 前回実行の残骸(__h)を消してから流し込む（古いdone状態の空読み防止）
osascript -e 'tell application "Safari" to do JavaScript "delete window.__h; delete window.__hStatus; 1" in document 1' >/dev/null 2>&1
osascript >/dev/null <<OSA
set js to (read POSIX file "$JS_FILE" as «class utf8»)
tell application "Safari" to do JavaScript js in document 1
OSA

# 保有中だけでなく売却済もページングするので、40秒では足りない（918枚で19ページ×2API）
OK=""
for i in $(seq 1 150); do
  DONE=$(osascript -e 'tell application "Safari" to do JavaScript "(window.__h&&window.__h.done)?(window.__h.error?(\"ERR \"+window.__h.error):\"ok\"):\"wait\"" in document 1' 2>/dev/null || echo "wait")
  case "$DONE" in
    ok) OK=1; break ;;
    ERR*) echo "✗ 収集エラー: $DONE"; exit 1 ;;
    *) sleep 1 ;;
  esac
done
if [ -z "$OK" ]; then
  echo "✗ 収集が時間内に終わりませんでした（途中結果は使いません）。"
  exit 1
fi

# __h.items を1行1JSONのJSONLで書き出す。
# ★区切りは String.fromCharCode(10) で作ること。"\n" と書いてはいけない。
#   osascript -e に渡した \n は AppleScript が**本物の改行**に変えてから JS に渡すため、
#   JS 側は文字列リテラルの途中で改行した SyntaxError になる。do JavaScript は
#   これを空文字で返し、rc=0・stderr も空なので**無言で0件**になる（2026-09-02に判明）。
osascript -e 'tell application "Safari" to do JavaScript "window.__h.items.map(function(x){return JSON.stringify(x)}).join(String.fromCharCode(10))" in document 1' > "$JSONL"

LINES=$(grep -c . "$JSONL" 2>/dev/null || echo 0)
if [ "$LINES" -eq 0 ]; then
  echo "✗ 画像URLを1件も取り出せませんでした。取り込みは行いません。"
  echo "  Safariの 開発 >「Apple EventsからのJavaScriptを許可」を確認してください。"
  rm -f "$JSONL"
  exit 1
fi
echo "▶ 収集 $LINES 件。未取得分をダウンロードします…"
"$PY" import_from_web.py "$JSONL"
rm -f "$JSONL"
