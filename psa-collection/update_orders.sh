#!/bin/bash
# PSA My Orders（グレーディング申請一覧）を data/orders.json に取り込む。
#
# 前提:
#   - Safari 設定 > 詳細 >「Web開発者用の機能を表示」
#     → 開発メニュー >「Apple EventsからのJavaScriptを許可」ON
#   - psacard.com にログイン済み
#
# 仕組み: ログイン済みSafariのタブで harvest_orders.js を実行し、
#         サイト内部の tRPC API(orders.list) を叩いて JSON を取り出す。
set -e
cd "$(dirname "$0")"
JS_FILE="$(pwd)/harvest_orders.js"
OUT="$(pwd)/data/orders.json"
mkdir -p data

echo "▶ Safari で PSA My Orders を開いています…"
open -a Safari "https://www.psacard.com/myaccount/myorders"
sleep 5

# ログイン確認（signin にリダイレクトされていないか）
URL=$(osascript -e 'tell application "Safari" to return URL of document 1' 2>/dev/null || echo "")
case "$URL" in
  *psacard.com*) : ;;
  *) echo "✗ psacard.com のページが前面にありません（URL=$URL）。ログインして My Orders を開いてから再実行してください。"; exit 1 ;;
esac
if echo "$URL" | grep -qi "signin\|login"; then
  echo "✗ 未ログインです（$URL）。psacard.com にログインしてから再実行してください。"
  exit 1
fi

echo "▶ 申請一覧を取得中…"
osascript >/dev/null <<OSA
set js to (read POSIX file "$JS_FILE" as «class utf8»)
tell application "Safari" to do JavaScript js in document 1
OSA

# window.__ord.done を最大20秒ポーリング
for i in $(seq 1 20); do
  DONE=$(osascript -e 'tell application "Safari" to do JavaScript "(window.__ord&&window.__ord.done)?(window.__ord.error?(\"ERR \"+window.__ord.error):\"ok\"):\"wait\"" in document 1' 2>/dev/null || echo "wait")
  case "$DONE" in
    ok) break ;;
    ERR*) echo "✗ 取得エラー: $DONE"; exit 1 ;;
    *) sleep 1 ;;
  esac
done

# 結果を書き出し
osascript -e 'tell application "Safari" to do JavaScript "JSON.stringify(window.__ord.data)" in document 1' > "$OUT" 2>/dev/null

# 検証
READ=$(python3 -c "import json; d=json.load(open('$OUT')); print(len(d.get('orders',[])), len(d.get('cards',[])))" 2>/dev/null || echo "0 0")
ORDERS=$(echo "$READ" | cut -d' ' -f1)
CARDS=$(echo "$READ" | cut -d' ' -f2)
if [ "$ORDERS" = "0" ]; then
  echo "✗ orders.json が空です。ログイン状態と権限設定を確認してください。"
  exit 1
fi
echo "✔ 完了: オーダー $ORDERS 件 / 鑑定中カード $CARDS 枚 を data/orders.json に保存しました。"
