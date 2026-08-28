#!/bin/bash
# にゃんこ大脱出をローカルで開く（動作確認用）。
#
# なぜ要るのか: 書体（assets/fonts/*.woff2）は file:// では読み込みが止まることがあり、
# 「手元では豆腐にならないのに、実際は豆腐」を取り違える。必ず HTTP で見る。
#
#   ./run.sh                → http://127.0.0.1:8543
#   ../app-start.sh neko-escape --shot   → 起動して画面も撮る
#
# ★ 127.0.0.1 固定（ゲームは社内LANに出さない）。--port 8543
# ★配信するのは www/（Capacitor の webDir）。本体はここにある
cd "$(dirname "$0")/www" || exit 1
exec /usr/bin/python3 -m http.server 8543 --bind 127.0.0.1
