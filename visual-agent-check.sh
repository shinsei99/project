#!/bin/bash
# 共通Visual Agent（Claude Codeがブラウザを見て操作する機能）が、このPCで動くかを確かめる。
#   使い方:  ./visual-agent-check.sh
# 引き継ぎ時・調子が悪いときに、まずこれを走らせる。詳細は VISUAL_AGENT.md。
set -u
cd "$(dirname "$0")"
ng=0
ok()   { printf '  ✅ %s\n' "$1"; }
bad()  { printf '  ❌ %s\n' "$1"; ng=$((ng+1)); }
warn() { printf '  ⚠️  %s\n' "$1"; }

echo "== 1. 定義ファイル =="
if [ -f "$HOME/.mcp.json" ]; then
  if grep -q '@playwright/mcp' "$HOME/.mcp.json"; then
    ok "~/.mcp.json あり（playwright の定義を確認）"
  else
    bad "~/.mcp.json はあるが playwright の定義が無い"
  fi
else
  bad "~/.mcp.json が無い → git pull で取得する（gitに入っている）"
fi

echo "== 2. 前提のソフト =="
if command -v claude >/dev/null; then ok "claude $(claude --version 2>/dev/null | head -1)"
else bad "claude CLI が無い"; fi

if command -v npx >/dev/null; then
  v=$(node -v 2>/dev/null)
  major=${v#v}; major=${major%%.*}
  if [ "${major:-0}" -ge 18 ]; then ok "node $v / npx あり"
  else bad "node $v は古い（@playwright/mcp は 18 以上が必要）"; fi
else
  bad "npx が無い → Node.js を入れる（brew install node）"
fi

if [ -d "/Applications/Google Chrome.app" ]; then ok "Google Chrome あり"
else bad "Google Chrome が無い → 入れるか、~/.mcp.json の --browser を chromium 等に変える"; fi

echo "== 3. MCPサーバーの起動（初回はダウンロードで1分ほどかかる） =="
if npx -y @playwright/mcp@0.0.79 --help >/dev/null 2>&1; then
  ok "Playwright MCP を起動できる"
else
  bad "Playwright MCP を起動できない（ネットワーク / npm の設定を確認）"
fi

if [ "$ng" -gt 0 ]; then
  echo; echo "❌ $ng 件の問題があります。上の指示に従って直してから、もう一度実行してください。"
  exit 1
fi

echo "== 4. 実際にブラウザで動かす（最終確認） =="
tmp=$(mktemp -d)
cat > "$tmp/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>チェック</title>
<h1 id="t">Visual Agent 動作確認</h1>
<button onclick="document.getElementById('t').textContent='クリック成功'">押す</button>
HTML
( cd "$tmp" && python3 -m http.server 8897 --bind 127.0.0.1 >/dev/null 2>&1 & echo $! > "$tmp/pid" )
sleep 2
echo "  テストページを開いてボタンを押させています…"
out=$(claude -p "http://127.0.0.1:8897/index.html を開き、ボタンを押して見出しの文字が変わることを確認し、変化後の見出しの文字だけを1行で答えてください。" \
  --output-format json --dangerously-skip-permissions --model sonnet \
  --mcp-config "$HOME/.mcp.json" --strict-mcp-config 2>/dev/null \
  | python3 -c "import json,sys;print(json.load(sys.stdin).get('result',''))" 2>/dev/null)
kill "$(cat "$tmp/pid")" 2>/dev/null; rm -rf "$tmp"

if printf '%s' "$out" | grep -q "クリック成功"; then
  echo "  ✅ ブラウザを開く・クリックする・結果を読む、すべて成功"
  echo; echo "🎉 このPCで Visual Agent が使えます。 cd ~ && claude で有効です。"
else
  echo "  ❌ ブラウザ操作に失敗しました。AIの返答: ${out:-（応答なし）}"
  echo; echo "対処: 対話セッション（cd ~ && claude）を一度起動し、"
  echo "      「.mcp.json のMCPサーバーを使うか」と聞かれたら承認してください（PCごとに1回だけ）。"
  exit 1
fi
