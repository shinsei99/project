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
HOST=$(hostname -s)
# ★tar名にホスト名を入れる。以前は両PCが同じ `apps-secrets.tar` へ書いていたため、
#   **メイン→サブとサブ→メインを同じ日にやると、先の書き出しを消してしまう**（2026-08-18に修正）。
TAR="$OUT_DIR/apps-secrets-$HOST.tar"

# import で使う「相手が書き出したtar」を選ぶ。自分のホスト名のものは無視し、新しい順で最初の1つ。
peer_tar() {
  local t
  for t in $(ls -t "$OUT_DIR"/apps-secrets-*.tar "$OUT_DIR"/apps-secrets.tar 2>/dev/null); do
    case "$t" in
      *"apps-secrets-$HOST.tar") continue ;;      # 自分が書いたものは取り込まない
    esac
    echo "$t"; return 0
  done
  return 1
}
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
    # ★SQLite は WAL に書きかけが残る。固める前にチェックポイントして本体へ流し込む
    #   （失敗しても -wal ごと運ぶので壊れない。-shm は再生成される作業用なので入れない）
    while IFS= read -r db; do
      /usr/bin/python3 - "$db" <<'PYEOF' 2>/dev/null || echo "  ⚠️  チェックポイントできず（-wal ごと運びます）: $db"
import sqlite3, sys
c = sqlite3.connect(sys.argv[1]); c.execute("PRAGMA wal_checkpoint(TRUNCATE)"); c.close()
PYEOF
    done < <(for p in "${files[@]}"; do find "$p" -name '*.db' 2>/dev/null; done)
    tar cf "$TAR" --exclude='*-shm' "${files[@]}" || { echo "tar に失敗"; exit 1; }
    date "+%Y-%m-%d %H:%M %z ($HOST) で書き出し" | tee "${TAR%.tar}.txt" > "$OUT_DIR/LAST_EXPORT.txt"
    echo
    echo "✅ $TAR （$(du -h "$TAR" | cut -f1)）"
    echo "   Dropboxの同期が終わってから、もう一方のPCで ./secrets-sync.sh import"
    ;;

  import)
    SRC_TAR=$(peer_tar) || { echo "相手が書き出した tar が見つかりません（$OUT_DIR）" >&2;
                             echo "先に持っている側で ./secrets-sync.sh export を実行してください"; exit 1; }
    echo "── 取り込み元: $(basename "$SRC_TAR")"
    echo "── $(cat "${SRC_TAR%.tar}.txt" 2>/dev/null || cat "$OUT_DIR/LAST_EXPORT.txt" 2>/dev/null || echo '（書き出し日時 不明）')"
    added=0; skipped=0
    tmp=$(mktemp -d)
    tar xf "$SRC_TAR" -C "$tmp" || { echo "展開に失敗"; rm -rf "$tmp"; exit 1; }
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
