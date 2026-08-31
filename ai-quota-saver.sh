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
#
# ★節約中は **Fable を使わない**（2026-09-01 オーナー指示）。
#   枠のゲージは入れ子で、「全モデル」と「Fableのみ」は**どちらか**ではない。
#   Fable を使うと**両方**減り、しかも 1トークンの重さが **Opus の倍**（$10/$50 対 $5/$25）。
#   ＝「Fableのみが減っていないから余っている」ではなく、**使うと全モデル側が最速で減る**。
#   自動処理は全部 `sonnet` に固定してあるので、下の点検は「うっかり足した」を見つける係。
set -eu
MARK="$HOME/.ai-quota-saver"
REPO="$(cd "$(dirname "$0")" && pwd)"

_until() {   # 期限を取り出す（無ければ空）
  [ -f "$MARK" ] || return 0
  grep -v '^#' "$MARK" 2>/dev/null | head -1 | tr -d ' \t'
}

_fable_hits() {  # 実行されるファイルの中に Fable の指定が無いか
  # ★探す範囲は **git の管理下だけ**（`git ls-files`）。
  #   このリポジトリの作業ツリーはホーム直下なので、素の `grep -r` を掛けると
  #   Library や CloudStorage（46GBの原本）まで舐めて数分帰ってこない（2026-09-01 実測）。
  #   .md は文章として Fable の話を書いてあるので見ない（自分自身が引っかかる）。
  ( cd "$REPO" 2>/dev/null || exit 0
    git ls-files -z -- '*.py' '*.sh' '*.js' '*.ts' '*.json' '*.plist' 2>/dev/null \
      | xargs -0 grep -En -e '--model[[:space:]="'"'"']*fable' -e 'claude-fable-[0-9]' 2>/dev/null
  ) || true
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
      echo "  ★節約中は Fable を使わない（全モデル枠を Opus の倍の速さで食う）"
      hits="$(_fable_hits)"
      if [ -n "$hits" ]; then
        echo "  ⚠️ Fable の指定が見つかった。sonnet に直すこと:" >&2
        printf '     %s\n' "$hits" >&2
      else
        echo "  Fable の指定: なし（自動処理は全部 sonnet）"
      fi
    elif [ -f "$MARK" ]; then
      echo "節約モード: OFF（期限 $(_until) を過ぎたので自動で戻っている）"
    else
      echo "節約モード: OFF（通常運転）"
    fi
    ;;
esac
