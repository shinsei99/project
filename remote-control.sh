#!/bin/bash
# 外出先のスマホ（Claudeアプリ）から繋ぐための Remote Control セッションを
# ターミナルの窓を1枚も開かずに立ち上げる。launchd（com.shinsei.claude-remote-control）から呼ばれる。
#
# 使い方（手で試すとき）:
#   ./remote-control.sh メインPC        … 1本立てる
#   ./remote-control.sh --status        … いま生きているか見る
#   ./remote-control.sh --stop          … 止める
#
# ★なぜ script(1) を噛ませるか（2026-09-02 実測）
#   claude --remote-control は対話セッションなので端末(TTY)が要る。
#   nohup で直に起動すると --print 扱いになり、次のエラーで即終了する:
#     Error: Input must be provided either through stdin or as a prompt argument when using --print
#   script が疑似端末を用意するので、窓なしでも対話セッションとして起動できる。
#
# ★なぜ最初に Enter を送るか
#   /Users/apple は hasTrustDialogAccepted=false なので、起動直後に
#   「Is this a project you created or one you trust?」で止まる。既定の「1. Yes」を選ぶ。
#   起動の速さが日によって違うので、8秒・15秒・25秒の3回送る
#   （信頼済みになった後の空 Enter は何も起きないので無害）。

set -u

NAME="${1:-メインPC}"
LOGDIR="$HOME/.remote-control"
LOG="$LOGDIR/session.log"
PATTERN="claude --remote-control"

case "$NAME" in
  --status)
    if pgrep -f "$PATTERN" >/dev/null 2>&1; then
      echo "起動中:"
      pgrep -fl "$PATTERN" | grep -v "script -q"
    else
      echo "起動していない"
    fi
    exit 0
    ;;
  --stop)
    # ★親（このスクリプトの常駐分）ごと倒すこと（2026-09-03 に踏んだ）。
    #   claude と script だけを殺すと、stdin を供給している無限ループが生き残り、
    #   親はパイプの終了を待ち続ける＝launchd からは「実行中」に見える。
    #   その結果 **KeepAlive が働かず、セッションが二度と戻らなかった**。
    if [ -f "$LOGDIR/wrapper.pid" ]; then
      W="$(cat "$LOGDIR/wrapper.pid" 2>/dev/null)"
      # 供給側の無限ループ（子）→ 親 の順に倒す。孤児の sleep を残さないため
      if [ -n "$W" ] && kill -0 "$W" 2>/dev/null; then
        for c in $(pgrep -P "$W" 2>/dev/null); do
          pkill -P "$c" 2>/dev/null
          kill "$c" 2>/dev/null
        done
        kill "$W" 2>/dev/null
      fi
      rm -f "$LOGDIR/wrapper.pid"
    fi
    pkill -f "$PATTERN" 2>/dev/null
    pkill -f "script -q $LOG" 2>/dev/null
    echo "止めた（launchd に登録済みなら KeepAlive で立ち上がり直す）"
    exit 0
    ;;
esac

# launchd は PATH が空なので張り直す（2026-08-28 のOCR全滅と同じ型を踏まないため）。
#
# ★並び順が肝（2026-09-02 に踏んだ）。claude は2か所にあり、
#     /opt/homebrew/bin/claude … 動く方（普段のログインシェルはこれを使っている）
#     /usr/local/bin/claude    … 壊れている npm 版。起動すると
#                                「Error: claude native binary not installed.」で即死する
#   /usr/local/bin を先に置くと壊れた方を掴む。homebrew を必ず先にすること。
export PATH="/opt/homebrew/bin:/opt/homebrew/sbin:$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

CLAUDE_BIN="$(command -v claude || true)"
if [ -z "$CLAUDE_BIN" ]; then
  echo "claude が見つからない（PATH=$PATH）" >&2
  exit 1
fi
# 壊れた方を掴んでいないか、起動前に確かめる
if ! "$CLAUDE_BIN" --version >/dev/null 2>&1; then
  echo "claude が起動できない: $CLAUDE_BIN" >&2
  exit 1
fi

# Claude Code の中から起動したときに引き継がれる印を外す。
# 付いたままだと子セッション扱いになり「Transcript saving is off」で履歴が残らない。
unset CLAUDECODE CLAUDE_CODE_CHILD_SESSION CLAUDE_CODE_ENTRYPOINT CLAUDE_CODE_SSE_PORT

mkdir -p "$LOGDIR"
: > "$LOG"   # 毎回まっさらにする（TUIの再描画でログが肥大するため）

cd "$HOME" || exit 1

# stdin を開けたままにする。閉じる（EOF）とセッションも終わってしまう。
#
# ★パイプで繋いではいけない（2026-09-03 に実際に止まった）。
#   もとは `{ …; while :; do sleep 3600; done } | script …` だった。この形だと、
#   毎朝5:00 の `--stop` が **claude と script だけを殺し、左側の無限ループは生き残る**。
#   親（このスクリプト）はパイプ全体の終了を待ち続けるので、**プロセスとしては「実行中」のまま**。
#   launchd は親しか見ていないため **KeepAlive が働かず、セッションが二度と戻らなかった**
#   （9/2 10:24 起動 → 9/3 05:00 に中身だけ死亡 → 朝は画面ごと消えた状態）。
#
#   ★FIFO で渡す形は**使えない**（同日に試して失敗）。`script` は stdin が FIFO だと
#     `script: tcgetattr/ioctl: Operation not supported on socket` で即死し、
#     KeepAlive と相まって9回クラッシュして launchd に throttle された。
#     パイプなら通るので、**パイプのまま**にして「止め方」の側を直す。
#
#   → このスクリプト自身の PID を控えておき、`--stop` が**親ごと**倒す。
#     親が終われば KeepAlive が立て直す＝毎朝の「まっさらにする」が意図どおり働く。
echo $$ > "$LOGDIR/wrapper.pid"

# stdin を開けたままにする。閉じる（EOF）とセッションも終わってしまう。
{
  for t in 8 7 10; do
    sleep "$t"
    printf '\r'
  done
  while :; do sleep 3600; done
} | script -q "$LOG" "$CLAUDE_BIN" --remote-control "$NAME"
