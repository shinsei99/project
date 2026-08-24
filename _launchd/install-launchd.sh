#!/bin/bash
# ============================================================
# launchd 登録スクリプト（社内LAN常時起動アプリ 全登録）
#   メインPC・サブPC 両方で使える。git pull 後にこれを実行するだけ。
#   $HOME を使うのでユーザー名に依存しない。冪等（何度実行してもOK）。
#   実体は各アプリの run.sh（Python は初回 .venv 自動作成、Node は npm install→build）。
# ============================================================
set -e

LA="$HOME/Library/LaunchAgents"
LOGS="$HOME/Library/Logs"
mkdir -p "$LA" "$LOGS"

# 対象: "ラベル|アプリフォルダ名"（CLAUDE.md の社内LAN常時起動ポート一覧と1対1対応）
APPS=(
  "com.shinsei.quote-generator|quote-generator"                 # 8503 ※別リポ shinsei99/quote-generator（独自deploy/キット有・main pullには含まれない。別PCは個別clone）
  "com.shinsei.property-notice-generator|property-notice-generator" # 8504
  "com.shinsei.maisoku-converter|maisoku-converter"             # 8505
  "com.shinsei.photo-inpainter|photo-inpainter"                 # 8506 ※初回は torch 等で .venv が 1.3GB・数分かかる
  "com.shinsei.realestate-calc|realestate-calc"                 # 8507 (静的PWA/npx serve)
  "com.shinsei.restoration-calculator|restoration-calculator"   # 8508
  "com.shinsei.realestate-valuation|realestate-valuation"       # 8509
  "com.shinsei.settlement-creator|settlement-creator"           # 8510
  "com.shinsei.madori-tracer|madori-tracer"                     # 8511
  "com.shinsei.madori-tracer-editor|madori-tracer/editor"       # 5175 (Vite/Node)
  "com.shinsei.theta-viewer|theta-viewer"                       # 8512 (Vite/Node)
  "com.shinsei.theta-viewer-api|theta-viewer/server"            # 8523 (Express/Node)
  "com.shinsei.tokuyaku-generator|tokuyaku-generator"           # 8513
  "com.shinsei99.payment-reconciler|payment-reconciler"         # 8514 (ラベルはshinsei99が正)
  "com.shinsei.image-resizer|image-resizer"                     # 8515
  "com.shinsei.tsuikyaku-crm|tsuikyaku-crm"                     # 8516
  "com.shinsei.baikai-generator|baikai-generator"               # 8517
  "com.shinsei.owner-payout-tracker|owner-payout-tracker"       # 8519
  "com.shinsei.file-finder|file-finder"                         # 8520
  "com.shinsei.gyomu-manual|gyomu-manual"                       # 8521
  "com.shinsei.parking-map|parking-map"                         # 8522 (serve.py --daemon)
  "com.shinsei.memorandum-generator|memorandum-generator"       # 8524
  "com.shinsei.soufu-maker|soufu-maker"                         # 8525 (不動産・新規)
  "com.shinsei.ai-ticket-counter|ai-ticket-counter"             # 8600 (uvicorn/FastAPI)
  "com.shinsei.kaitori-dm-maker|kaitori-dm-maker"               # 8526 ※ツール・localhost・社内共有なし（常時起動のみ）
  "com.shinsei.psa-collection|psa-collection"                   # 8527 ※ツール・localhost・社内共有なし（常時起動のみ）
  "com.shinsei.shorui-cabinet|shorui-cabinet"                   # 8528 ※不動産・自分専用・localhost（常時起動のみ）
)

# **カード図鑑2本（pokecard-dex 8531 / onepiece-dex 8537）は常駐させない**
# （2026-08-24 オーナー判断）。常設するのは PSAカード管理（8527）だけで、図鑑は
# その中から開いて使う。PSA管理は図鑑の app.py を**モジュールとして直接読み込む**ので、
# 8531 / 8537 が起動していなくても中から使える（実機で確認済み）。
# 単独の画面が要るときだけ各アプリの ./run.sh を都度叩く。

for entry in "${APPS[@]}"; do
  LABEL="${entry%%|*}"
  DIR="$HOME/${entry##*|}"
  PLIST="$LA/$LABEL.plist"

  if [ ! -f "$DIR/run.sh" ]; then
    echo "!! $DIR/run.sh が無い（git pull 済みか確認）。スキップ: $LABEL"
    continue
  fi
  chmod +x "$DIR/run.sh"

  cat > "$PLIST" <<PLISTEOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>Label</key>
	<string>$LABEL</string>
	<key>ProgramArguments</key>
	<array>
		<string>/bin/bash</string>
		<string>$DIR/run.sh</string>
	</array>
	<key>WorkingDirectory</key>
	<string>$DIR</string>
	<key>RunAtLoad</key>
	<true/>
	<key>KeepAlive</key>
	<true/>
	<key>StandardOutPath</key>
	<string>$LOGS/$LABEL.log</string>
	<key>StandardErrorPath</key>
	<string>$LOGS/$LABEL.err.log</string>
</dict>
</plist>
PLISTEOF

  plutil -lint "$PLIST" >/dev/null
  launchctl unload "$PLIST" 2>/dev/null || true
  launchctl load "$PLIST"
  echo "OK: $LABEL 登録・起動（$DIR/run.sh）"
done

echo
echo "=== launchd 登録確認 ==="
launchctl list | grep -E "com.shinsei" || echo "(まだ起動処理中の可能性あり)"
echo
echo "※ Streamlit/FastAPI系は初回 .venv 自動作成のため、ポートが上がるまで数十秒〜数分かかることがあります。"
echo "※ Node系（realestate-calc/theta-viewer/theta-viewer-api/madori-tracer-editor）は Node.js/npm が必須。"
echo "   未導入だと該当アプリのみ起動失敗します（brew install node 後に再実行）。初回は npm install→build で数分かかります。"
echo "※ gyomu-manual は python3 の標準モジュールのみ使用（即時起動）。"
