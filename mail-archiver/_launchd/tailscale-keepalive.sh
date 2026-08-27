#!/bin/bash
# Tailscale が止まっていたら起こす（5分ごとに見張る）。
#
# なぜ要るのか（2026-08-28に2回起きた）:
#   Tailscale.app は **自動起動の設定に一切入っていなかった**（launchd登録もログイン項目も無し）。
#   そのため手で起こしたときしか動かず、落ちるとスマホからメールアーカイバ
#   （https://usermac-mini.tailfcc81a.ts.net → 127.0.0.1:8535）に届かなくなる。
#   管理画面では Mac mini が `not connected` に見える。
#
# ★ここでやるのは「アプリを起こす」だけ。ログインや接続設定には触らない
#   （認証はアプリが持っている。tailscale up も叩かない）。
#
# ★紛らわしい罠: 止まっていると `serve status` が `No serve config` と出るが、
#   **設定は消えていない**。起こせば戻る。慌てて serve を張り直さないこと。
TS="/Applications/Tailscale.app/Contents/MacOS/Tailscale"
LOG="$HOME/Library/Logs/com.shinsei.tailscale-keepalive.log"

[ -x "$TS" ] || { echo "[$(date '+%F %T')] Tailscale.app が見つからない" >> "$LOG"; exit 0; }

if "$TS" status >/dev/null 2>&1; then
  exit 0            # 動いている。何もしない（ログも汚さない）
fi

echo "[$(date '+%F %T')] 止まっていたので起こす" >> "$LOG"
open -a Tailscale
sleep 10
if "$TS" status >/dev/null 2>&1; then
  echo "[$(date '+%F %T')] 復旧した: $("$TS" serve status 2>&1 | head -1)" >> "$LOG"
else
  echo "[$(date '+%F %T')] ★起こせなかった。人が確認すること" >> "$LOG"
fi
