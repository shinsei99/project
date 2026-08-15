#!/bin/bash
# 機密引き継ぎ（メインPC→サブPC）: 個人Dropboxへ機密一式を書き出す。
# コードは git（公開リポ）で運ぶ。ここでは git に出せない機密のみを扱う:
#   .streamlit/secrets.toml / data/app.db（ナレッジ・TODO・履歴）/ 識別子入り内部docs / ngrok token
# ※会社共有ではなく「Dropbox-個人」に置く（他スタッフから見えない）。
set -e
cd "$(dirname "$0")"

DB_PERSONAL="$HOME/Library/CloudStorage/Dropbox-個人"
OUT="$DB_PERSONAL/chatwork-ai-manager-handoff"
if [ ! -d "$DB_PERSONAL" ]; then
  echo "個人Dropboxが見つかりません: $DB_PERSONAL" >&2; exit 1
fi
mkdir -p "$OUT"

TAR="$OUT/chatwork-ai-manager-secret.tar"
echo "機密をtarにまとめています…"
# 存在するものだけを含める
FILES=()
for f in .streamlit/secrets.toml data/app.db data/app.db-wal data/app.db-shm \
         CLAUDE.md TODO.md SESSION_LOG.md LINE_SETUP.md; do
  [ -e "$f" ] && FILES+=("$f")
done
tar cf "$TAR" "${FILES[@]}"

# ngrok の authtoken（別ファイルにコピー。個人Dropbox内なので機密扱い）
NGROK_YML="$HOME/Library/Application Support/ngrok/ngrok.yml"
[ -f "$NGROK_YML" ] && cp "$NGROK_YML" "$OUT/ngrok.yml"

SIZE=$(du -h "$TAR" | cut -f1)
cat > "$OUT/README-先に読む.txt" <<EOF
chatwork-ai-manager（AI業務マネージャー）機密引き継ぎ
====================================================
$(date '+%Y-%m-%d %H:%M')

このフォルダに入っているもの（会社共有ではなく個人Dropbox）
  chatwork-ai-manager-secret.tar  … 機密一式（$SIZE）
      .streamlit/secrets.toml   … Chatwork/LINE/ngrok/国交省 の各トークン・許可userId
      data/app.db(+wal/shm)     … ナレッジ索引・TODO・案件・処理済みメッセージ・定時履歴
      CLAUDE.md/TODO.md/SESSION_LOG.md/LINE_SETUP.md … 内部ドキュメント（識別子を含むためgit外）
  ngrok.yml                       … ngrok authtoken（あれば）

コードは GitHub（shinsei99/project）にあります。
  cd ~ && git pull origin main       → chatwork-ai-manager/ に .py 等が入る

サブPCでのセットアップ手順
  1) cd ~ && git pull origin main
  2) cd ~/chatwork-ai-manager && bash handoff_import.sh   （このtarを展開）
  3) 依存: /usr/bin/python3 -m pip install --user -r requirements.txt
  4) claude CLI にログイン済みであること（MAXプラン）
  5) ngrok: cp ngrok.yml へ or  ngrok config add-authtoken <token>
  6) 起動（常駐）: bash install-launchd.sh
  7) 確認: curl -s -o /dev/null -w '%{http_code}' http://localhost:8529/  → 200

⚠️ 重要（二重起動の禁止）
  worker と ngrok は「同時に1台のPCだけ」で動かすこと。
  2台同時だと ①Chatwork/LINEに二重返信 ②ngrok固定ドメインの取り合い が起きる。
  サブPCで動かす前に、メインPCで以下を停止:
    launchctl unload ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager*.plist
EOF

echo "完了: $OUT"
echo "  - chatwork-ai-manager-secret.tar ($SIZE)"
echo "  - README-先に読む.txt"
[ -f "$OUT/ngrok.yml" ] && echo "  - ngrok.yml"
echo ""
echo "⚠️ サブPCで動かす前に、メインPC側を停止すること（二重起動防止）。"
