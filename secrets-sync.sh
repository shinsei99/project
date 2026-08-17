#!/bin/bash
# 機密・データをPC間で運ぶ。**コードはgit、機密は個人Dropbox**という切り分けを守るための道具。
#
#   ./secrets-sync.sh check     # このPCに何が無いかを出す（どちらのPCでも）
#   ./secrets-sync.sh export    # 持っている側（=メインPC）で実行。Dropboxへ書き出す
#   ./secrets-sync.sh import    # 欲しい側（=サブPC）で実行。Dropboxから取り込む
#   ./secrets-sync.sh import --force   # 既にある物も上書きする（既定は上書きしない）
#
# 運ぶ対象は `secrets-manifest.txt` に書いてある。**新しく .env を作ったらそこに追記する。**
# 置き場は「Dropbox-個人」。会社共有の方に置くと他スタッフから見えるので使わない。
#
# ※ chatwork-ai-manager だけは専用の handoff_export.sh / handoff_import.sh を使う
#   （DB 170MB＋常駐の切り替えが絡むため）。
set -uo pipefail
cd "$(dirname "$0")"

DB_PERSONAL="$HOME/Library/CloudStorage/Dropbox-個人"
OUT_DIR="$DB_PERSONAL/apps-secrets-handoff"
TAR="$OUT_DIR/apps-secrets.tar"
MANIFEST="secrets-manifest.txt"
CMD="${1:-check}"
FORCE=0
[ "${2:-}" = "--force" ] && FORCE=1

[ -f "$MANIFEST" ] || { echo "$MANIFEST がありません"; exit 1; }

# コメントと空行を除いたパス一覧
paths() { grep -v '^\s*#' "$MANIFEST" | grep -v '^\s*$'; }

case "$CMD" in
  check)
    have=0; miss=0
    echo "── このPCの状態（$(hostname -s)）"
    while IFS= read -r p; do
      if [ -e "$p" ]; then
        printf "  ✅ %-46s %s\n" "$p" "$(du -sh "$p" 2>/dev/null | cut -f1)"
        have=$((have+1))
      else
        printf "  ❌ %-46s 無い\n" "$p"
        miss=$((miss+1))
      fi
    done < <(paths)
    echo
    echo "ある $have / 無い $miss"
    if [ $miss -gt 0 ]; then
      echo "→ 持っている側のPCで  ./secrets-sync.sh export   を実行し、"
      echo "   このPCで          ./secrets-sync.sh import   を実行する"
    fi
    ;;

  export)
    [ -d "$DB_PERSONAL" ] || { echo "個人Dropboxが見つかりません: $DB_PERSONAL" >&2; exit 1; }
    mkdir -p "$OUT_DIR"
    files=()
    while IFS= read -r p; do
      [ -e "$p" ] && files+=("$p")
    done < <(paths)
    [ ${#files[@]} -eq 0 ] && { echo "書き出すものがありません"; exit 1; }
    echo "── ${#files[@]}件をまとめています"
    printf '  %s\n' "${files[@]}"
    tar cf "$TAR" "${files[@]}" || { echo "tar に失敗"; exit 1; }
    date "+%Y-%m-%d %H:%M %z ($(hostname -s)) で書き出し" > "$OUT_DIR/LAST_EXPORT.txt"
    echo
    echo "✅ $TAR （$(du -h "$TAR" | cut -f1)）"
    echo "   Dropboxの同期が終わってから、もう一方のPCで ./secrets-sync.sh import"
    ;;

  import)
    [ -f "$TAR" ] || { echo "書き出しが見つかりません: $TAR" >&2; echo "先に持っている側で export を実行してください"; exit 1; }
    echo "── $(cat "$OUT_DIR/LAST_EXPORT.txt" 2>/dev/null || echo '（書き出し日時 不明）')"
    added=0; skipped=0
    tmp=$(mktemp -d)
    tar xf "$TAR" -C "$tmp" || { echo "展開に失敗"; rm -rf "$tmp"; exit 1; }
    while IFS= read -r p; do
      src="$tmp/$p"
      [ -e "$src" ] || continue
      if [ -e "$p" ] && [ $FORCE -eq 0 ]; then
        printf "  ⏭  %-46s すでにある（上書きしない）\n" "$p"
        skipped=$((skipped+1))
        continue
      fi
      mkdir -p "$(dirname "$p")"
      rm -rf "$p"
      cp -R "$src" "$p"
      printf "  ✅ %-46s 取り込み\n" "$p"
      added=$((added+1))
    done < <(paths)
    rm -rf "$tmp"
    echo
    echo "取り込み $added / 既存のため据え置き $skipped"
    [ $skipped -gt 0 ] && echo "→ 上書きしたい場合は ./secrets-sync.sh import --force"
    ;;

  *)
    echo "使い方: ./secrets-sync.sh {check|export|import [--force]}"
    exit 1
    ;;
esac
