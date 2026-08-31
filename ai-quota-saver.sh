#!/bin/bash
# claude の定額枠を節約するモードの切り替え（2026-08-31 オーナー指示「枠が少ない」）。
#
#   ./ai-quota-saver.sh on      節約モードにする（claudeを使う夜間処理を止める）
#   ./ai-quota-saver.sh off     元に戻す
#   ./ai-quota-saver.sh         いまどちらか
#
# **印はこのファイル1つだけ**: ~/.ai-quota-saver（中身は理由のメモ）。
# 夜間ジョブ側が起動時にこれを見て、claude を使う工程を飛ばす。
# **launchd を外さない**（外すと戻し忘れて永久に止まる）。印を消せば翌晩から自動で戻る。
#
# 止まるもの（claudeを使う夜間処理）:
#   1. 共有フォルダOCRの claude 回送 … macOS Vision で読めないものは**後日に回す**
#      （見送りリストには入れないので、枠が戻れば自動で再挑戦される）
#   2. 英語メールの日本語訳（mail-archiver / company-mail-archiver）
#   3. 記事の自動執筆（ai-tools-base の daily-write）
#      ※在庫が29本あり、Zennも上限で止まっているので、いま書いても出せない
#
# 止まらないもの（業務で使うので触らない）:
#   ・Chatwork/LINE の応答（AI業務マネージャーの worker）
#   ・画面からの「AIに探してもらう」
#   ・メールの取り込み・添付のOCR（macOS Vision＝無料）・ベクトル作成（ローカル）
set -eu
MARK="$HOME/.ai-quota-saver"

case "${1:-status}" in
  on)
    printf '節約モード（%s に設定）\nclaudeを使う夜間処理を止めています。戻すには ./ai-quota-saver.sh off\n' \
      "$(date '+%Y-%m-%d %H:%M')" > "$MARK"
    echo "節約モード: ON"
    echo "  止まるもの: 共有フォルダOCRのclaude回送 / 英語メールの翻訳 / 記事の自動執筆"
    echo "  動くもの  : Chatwork・LINEの応答 / AIに探してもらう / 取り込み・Vision OCR・ベクトル"
    ;;
  off)
    if [ -f "$MARK" ]; then
      mv "$MARK" "$MARK.off-$(date +%Y%m%d%H%M%S)"
      echo "節約モード: OFF（翌晩から元どおり）"
    else
      echo "もともと節約モードではありません"
    fi
    ;;
  *)
    if [ -f "$MARK" ]; then
      echo "節約モード: ON"
      cat "$MARK"
    else
      echo "節約モード: OFF（通常運転）"
    fi
    ;;
esac
