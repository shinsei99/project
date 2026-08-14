#!/bin/bash
# 全カード巡回の完走を待って、図鑑の仕上げまで一気に流す。
#
#   1. crawl_myca_cards.py が終わるまで待つ（落ちていたら再開させる）
#   2. 新しく見つかったカードの400px画像を取る
#   3. build_dex.py で図鑑を組み直す
#   4. check_dex.py で整合性を検査してログに残す
#   5. アプリを再起動する
#
# pgrep のパターンは [c] のように括っている。括らないとこのスクリプト自身の
# コマンド行にマッチして「まだ動いている」と誤判定し、永久に待ち続ける
# （実際にそれで待機ループが空回りした）。
#
# 使い方: nohup ./finish.sh > /tmp/finish.log 2>&1 &

cd "$(dirname "$0")" || exit 1
PY=.venv/bin/python
log() { echo "[$(date '+%m/%d %H:%M')] $*"; }

# 画面が寝ても止まらないように
pgrep -f "[c]affeinate" > /dev/null || (nohup caffeinate -dims > /dev/null 2>&1 &)

log "=== 巡回の完走を待ちます ==="
for round in $(seq 1 40); do
  # 動いているなら終わるまで待つ
  while pgrep -f "[c]rawl_myca_cards" > /dev/null; do sleep 60; done

  # 未取得が残っていないか確かめる。残っていれば再開（落ちた場合の保険）
  out=$($PY crawl_myca_cards.py 2>&1 | tr '\r' '\n')
  echo "$out" | tail -2
  if echo "$out" | grep -q "すべて取得済み"; then
    log "巡回は完走しました（$round 回目の確認）"
    break
  fi
  log "巡回を再開しました（$round 回目）"
done

log "=== 取得結果 ==="
sqlite3 data/cards.db "SELECT status||': '||COUNT(*) FROM myca_card GROUP BY status;"

# unparsed は「表記が未対応」だけでなく「取得が途中で切れた」ときにも出る。
# 実測では ID 265480（オトスパス）が1件だけ unparsed になり、取り直すと
# 普通に読めた。まず全部取り直して、それでも残るものが本当の未対応。
bad=$(sqlite3 data/cards.db "SELECT COUNT(*) FROM myca_card WHERE status='unparsed';")
if [ "$bad" -gt 0 ]; then
  log "未対応の表記が ${bad}件。まず取り直します"
  for cid in $(sqlite3 data/cards.db "SELECT card_id FROM myca_card WHERE status='unparsed';"); do
    $PY crawl_myca_cards.py --one "$cid" > /dev/null 2>&1
  done
  bad=$(sqlite3 data/cards.db "SELECT COUNT(*) FROM myca_card WHERE status='unparsed';")
fi
log "未対応の表記: ${bad}件（取り直したあと）"
if [ "$bad" -gt 0 ]; then
  log "⚠️ 本当に未対応の表記です。パーサに追加してください:"
  sqlite3 data/cards.db "SELECT card_id||'  '||IFNULL(name,'') FROM myca_card WHERE status='unparsed' LIMIT 10;"
fi

log "=== 新しいカードの400px画像を取ります ==="
$PY fetch_myca_large.py 2>&1 | grep -v Warning | tr '\r' '\n' | tail -3

log "=== 一覧用のサムネイルを作ります ==="
$PY make_thumbs.py 2>&1 | tail -2

log "=== 図鑑を組み直します ==="
$PY build_dex.py 2>&1 | tail -12

log "=== 整合性の検査 ==="
$PY check_dex.py 2>&1 | head -20
log "--- パック単位（正解表との照合）---"
$PY check_dex.py --packs 2>&1 | sed -n '/パック単位/,$p' | head -40

log "=== アプリを再起動します ==="
pkill -f "streamlit run app.py"
sleep 3
nohup ./run.sh > /tmp/dex_app.log 2>&1 &
sleep 15
code=$(curl -s -o /dev/null -w '%{http_code}' -m 20 http://127.0.0.1:8531)
log "アプリ HTTP $code（http://127.0.0.1:8531）"
log "=== すべて完了しました ==="
