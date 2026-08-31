#!/bin/bash
# claude の定額枠を節約するモード（2026-08-31 オーナー指示「枠が少ない」）。
#
#   ./ai-quota-saver.sh until 2026-09-04T06:00   その日時まで節約する
#   ./ai-quota-saver.sh off                      いま解除する
#   ./ai-quota-saver.sh                          いまどちらか
#   ./ai-quota-saver.sh check                    節約中なら終了コード0（夜間ジョブが使う）
#
# ★**期限つきにしてある**（Zennの静止期間と同じ作り）。
#   「on/off」だけだと戻し忘れて永久に止まる。日時を過ぎれば**勝手に元へ戻る**。
#   launchd は外さない（外したら戻し忘れる）。
#
# 印は `~/.ai-quota-saver` の1ファイルだけ。1行目に期限（ISO）、以下はコメント。
#
# 止まるもの（claudeを使う夜間処理）:
#   1. 共有フォルダOCRの claude 回送 … macOS Vision で読めないものは**後日に回す**
#      （見送りリストには入れないので、期限が切れれば自動で再挑戦される）
#   2. 英語メールの日本語訳（mail-archiver / company-mail-archiver）
#   3. 記事の自動執筆（ai-tools-base の daily-write）
#
# 止まらないもの（業務で使うので触らない）:
#   ・Chatwork/LINE の応答（AI業務マネージャーの worker）
#   ・画面からの「AIに探してもらう」
#   ・メールの取り込み・添付のOCR（macOS Vision＝無料）・ベクトル作成（ローカル）
set -eu
MARK="$HOME/.ai-quota-saver"

_until() {   # 期限を取り出す（無ければ空）
  [ -f "$MARK" ] || return 0
  grep -v '^#' "$MARK" 2>/dev/null | head -1 | tr -d ' \t'
}

_active() {  # 節約中か（0=節約中）
  local u; u="$(_until)"
  [ -n "$u" ] || return 1
  # ISO表記なので文字列比較で正しく並ぶ
  [ "$(date '+%Y-%m-%dT%H:%M')" \< "$u" ]
}

case "${1:-status}" in
  check)
    _active && exit 0 || exit 1
    ;;
  until)
    U="${2:?期限を指定してください（例: 2026-09-04T06:00）}"
    cat > "$MARK" <<EOF
$U
# ↑ この日時まで claude を使う夜間処理を止める（設定 $(date '+%Y-%m-%d %H:%M')）。
#
# 止まるもの: 共有フォルダOCRのclaude回送 / 英語メールの翻訳 / 記事の自動執筆
# 動くもの  : Chatwork・LINEの応答 / AIに探してもらう / 取り込み・Vision OCR・ベクトル
#
# ★期限を過ぎれば**勝手に元へ戻る**（launchdは外していない）。
#   前倒しで戻すなら ./ai-quota-saver.sh off
EOF
    echo "節約モード: ON（$U まで）"
    ;;
  on)
    echo "★期限を付けてください: ./ai-quota-saver.sh until 2026-09-04T06:00" >&2
    exit 2
    ;;
  off)
    if [ -f "$MARK" ]; then
      mv "$MARK" "$MARK.off-$(date +%Y%m%d%H%M%S)"
      echo "節約モード: OFF（次の夜間から元どおり）"
    else
      echo "もともと節約モードではありません"
    fi
    ;;
  *)
    if _active; then
      echo "節約モード: ON（$(_until) まで）"
    elif [ -f "$MARK" ]; then
      echo "節約モード: OFF（期限 $(_until) を過ぎたので自動で戻っている）"
    else
      echo "節約モード: OFF（通常運転）"
    fi
    ;;
esac
