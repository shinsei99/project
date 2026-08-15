#!/bin/bash
# ngrok 公開トンネル（LINE Webhook用・固定ドメイン）。line_webhook(8530)を公開HTTPS化。
# QUIC(UDP7844)がこの回線でブロックされるため --protocol http2 を明示。
# ドメインは secrets.toml の ngrok_domain から読む（公開gitに識別子を出さないため）。
cd "$(dirname "$0")"
export PATH="/opt/homebrew/bin:$HOME/.local/bin:/usr/local/bin:$PATH"
DOMAIN=$(/usr/bin/python3 -c "import sys;sys.path.insert(0,'.');from services import config;print(config.get('ngrok_domain') or '')" 2>/dev/null)
if [ -z "$DOMAIN" ]; then
  echo "[ngrok] secrets.toml の ngrok_domain が未設定です。停止します。" >&2
  exit 1
fi
exec ngrok http 8530 --url="https://${DOMAIN}" --log=stdout --log-format=logfmt
