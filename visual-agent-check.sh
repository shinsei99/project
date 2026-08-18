#!/bin/bash
# 共通Visual Agent（Claude Codeがブラウザを見て操作する仕組み）が、このPCで動くかを確かめる。
#   ./visual-agent-check.sh          入口A(MCP)と入口B(./va.sh)の両方
#   ./visual-agent-check.sh --mcp    入口Aだけ    --va  入口Bだけ
# 引き継ぎ時・調子が悪いときに、まずこれを走らせる。詳細は VISUAL_AGENT.md。
set -u
cd "$(dirname "$0")"
ng=0
ok()   { printf '  ✅ %s\n' "$1"; }
bad()  { printf '  ❌ %s\n' "$1"; ng=$((ng+1)); }

want_mcp=1; want_va=1
case "${1:-}" in
  --mcp) want_va=0 ;;
  --va)  want_mcp=0 ;;
  "" ) ;;
  *) echo "使い方: $0 [--mcp|--va]"; exit 2 ;;
esac

# テスト用のページを1つ立てて、両方の入口で同じものを見る（結果が食い違わないことも見る）
#
# ★2026-08-18のはまり: 前回の実行で残った http.server が同じポートを掴んだままだと、
#   **消えた一時ディレクトリを配り続けて全部404**になり、「クリックできない」と誤診する。
#   → 立てる前に必ず居座りを落とし、立てた後に curl で中身を確かめてから進む。
PORT=8897
pkill -f "http.server $PORT" 2>/dev/null; sleep 1
tmp=$(mktemp -d)
cat > "$tmp/index.html" <<'HTML'
<!doctype html><meta charset="utf-8"><title>チェック</title>
<h1 id="t">Visual Agent 動作確認</h1>
<button onclick="document.getElementById('t').textContent='クリック成功'">押す</button>
HTML
cd "$tmp" && python3 -m http.server $PORT --bind 127.0.0.1 >/dev/null 2>&1 &
srv=$!
cd "$(dirname "$0")"
# wait まで入れるのは、シェルが "Terminated: 15" と出すのを抑えるため
cleanup() { { kill "$srv"; wait "$srv"; } 2>/dev/null; pkill -f "http.server $PORT" 2>/dev/null; rm -rf "$tmp"; }
trap cleanup EXIT
for _ in 1 2 3 4 5 6 7 8 9 10; do
  sleep 0.5
  curl -fs "http://127.0.0.1:$PORT/index.html" | grep -q "Visual Agent 動作確認" && served=1 && break
done
if [ "${served:-0}" != 1 ]; then
  echo "  ❌ テスト用ページを立てられなかった（127.0.0.1:$PORT）。ポートの居座りを確認:"
  echo "     lsof -nP -iTCP:$PORT -sTCP:LISTEN"
  exit 1
fi

echo "== 0. 共通 =="
if command -v claude >/dev/null; then ok "claude $(claude --version 2>/dev/null | head -1)"
else bad "claude CLI が無い"; fi
if [ -d "/Applications/Google Chrome.app" ]; then ok "Google Chrome あり（両方の入口が同じChromeを使う）"
else echo "  ⚠️  Google Chrome が無い → 入口Bは同梱Chromiumに自動で切り替わる。入口Aは --browser を変える"; fi

if [ "$want_mcp" = 1 ]; then
  echo "== 1. 入口A: MCP（会話の中） =="
  if [ -f "$HOME/.mcp.json" ] && grep -q '@playwright/mcp' "$HOME/.mcp.json"; then
    ok "~/.mcp.json あり（playwright の定義を確認）"
  else
    bad "~/.mcp.json が無い/定義が入っていない → git pull で取得する（gitに入っている）"
  fi
  if command -v npx >/dev/null; then
    v=$(node -v 2>/dev/null); major=${v#v}; major=${major%%.*}
    if [ "${major:-0}" -ge 18 ]; then ok "node $v / npx あり"
    else bad "node $v は古い（@playwright/mcp は 18 以上が必要）"; fi
  else
    bad "npx が無い → Node.js を入れる（brew install node）"
  fi
fi

if [ "$want_va" = 1 ]; then
  echo "== 2. 入口B: ./va.sh（シェル） =="
  py=""
  for c in "${VA_PYTHON:-}" "agent-platform/.venv/bin/python" ".va-venv/bin/python" "/usr/bin/python3"; do
    [ -n "$c" ] && [ -x "$c" ] && "$c" -c "import playwright" 2>/dev/null && { py="$c"; break; }
  done
  if [ -n "$py" ]; then ok "Playwright(Python) あり: $py"
  else bad "Playwright(Python) が無い → python3 -m venv .va-venv && .va-venv/bin/pip install playwright && .va-venv/bin/playwright install chromium"; fi

  if [ -n "$py" ]; then
    ./va.sh stop >/dev/null 2>&1
    start_msg=$(./va.sh start 2>&1 | tail -1)
    if printf '%s' "$start_msg" | grep -q "起動した"; then
      ok "ブラウザ起動: $start_msg"
      ./va.sh goto "http://127.0.0.1:$PORT/index.html" >/dev/null 2>&1
      ./va.sh click "text=押す" >/dev/null 2>&1
      if ./va.sh text 2>/dev/null | grep -q "クリック成功"; then ok "開く→押す→読む、成功"
      else bad "クリックの結果を読み取れなかった"; fi
      shot=$(./va.sh shot va-check 2>/dev/null | tail -1)
      [ -n "$shot" ] && ok "スクリーンショット: $shot" || bad "スクリーンショットに失敗"
      ./va.sh check >/dev/null 2>&1 && ok "check（UI崩れの機械検出）が動く" || bad "check が動かない"
      ./va.sh stop >/dev/null 2>&1
    else
      bad "./va.sh start に失敗: $start_msg"
    fi
  fi
fi

if [ "$ng" -gt 0 ]; then
  echo; echo "❌ $ng 件の問題があります。上の指示に従って直してから、もう一度実行してください。"
  exit 1
fi

if [ "$want_mcp" = 1 ]; then
  echo "== 3. 入口A を実際に動かす（初回はダウンロードで1分ほどかかる） =="
  out=$(claude -p "http://127.0.0.1:$PORT/index.html を開き、ボタンを押して見出しの文字が変わることを確認し、変化後の見出しの文字だけを1行で答えてください。" \
    --output-format json --dangerously-skip-permissions --model sonnet \
    --mcp-config "$HOME/.mcp.json" --strict-mcp-config 2>/dev/null \
    | python3 -c "import json,sys;print(json.load(sys.stdin).get('result',''))" 2>/dev/null)
  if printf '%s' "$out" | grep -q "クリック成功"; then
    ok "AIだけでブラウザを開く・押す・読む、すべて成功"
  else
    bad "入口Aのブラウザ操作に失敗。AIの返答: ${out:-（応答なし）}"
    echo "     対処: 対話セッション（cd ~ && claude）を一度起動し、"
    echo "           「.mcp.json のMCPサーバーを使うか」に承認する（PCごとに1回だけ）"
  fi
fi

echo
if [ "$ng" -gt 0 ]; then
  echo "❌ $ng 件の問題があります。"; exit 1
fi
echo "🎉 このPCで共通Visual Agentが使えます（入口A: cd ~ && claude ／ 入口B: ./va.sh）。"
