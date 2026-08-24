#!/bin/bash
# ============================================================
# 別PCで図鑑のデータを一から作る。git pull のあとこれ1本でよい。
#
#   data/（画像4,962枚＝約1.2GB＋DB）は**gitに入っていない**ので、
#   別PCでは作り直す。全部やって40〜70分（ほぼ画像の取得時間）。
#
#   途中で止めても、もう一度叩けば続きから走る（どの段階も冪等で、
#   既にあるファイルは取りに行かない）。
#
#   使い方:  ./setup.sh            # 足りないものだけ作る
#            ./setup.sh --rebuild  # 図鑑テーブルだけ作り直す（取得はしない）
# ============================================================
set -e
cd "$(dirname "$0")"

PY=python3
[ -x .venv/bin/python ] && PY=.venv/bin/python

step() { echo; echo "── $* ────────────────────────────────"; }

if [ ! -d .venv ]; then
  step "0/7 .venv を作る"
  python3 -m venv .venv
  .venv/bin/pip install -q --upgrade pip
  .venv/bin/pip install -q -r requirements.txt
  PY=.venv/bin/python
fi

if [ "$1" = "--rebuild" ]; then
  step "図鑑テーブルだけ組み立て直す"
  $PY build_dex.py
  $PY check_dex.py
  exit 0
fi

step "1/7 公式カードリストを巡回（全62シリーズ・約1分）"
$PY crawl_official.py

step "2/7 公式の商品ラインナップを巡回（156件＋パッケージ画像・約1分）"
$PY crawl_products.py

step "3/7 カード画像を取得（4,962枚・約1.2GB・40〜60分）"
echo "   ※ ここが一番長い。既にあるファイルは取りに行かない"
$PY fetch_images.py

step "4/7 一覧用サムネイルを作る（180px）"
$PY make_thumbs.py

# **画像取得より後でなければならない。** この工程は典拠サイトの画像と
# `data/img` の手元の画像を見比べて「どの別イラストか」を決める。画像が1枚も
# 無い状態で走らせると照合が全部外れ、**0件のまま黙って成功する**
# （2026-08-24 メインPC: 画像取得より前に置いていたため super_parallel.json が
#  `{}` になり、スーパーパラレル51枚がレアリティから丸ごと抜けた）
step "5/7 スーパーパラレル系のレアリティを補完（外部の一覧＋画像照合）"
# 公式はこの区分を持っていない。失敗しても図鑑は動くので止めない
$PY fill_super_parallel.py || echo "!! 補完できなかった（典拠サイトが変わった可能性）。図鑑は動く"
SP_N=$($PY - <<'PYEOF'
import json, os
p = os.path.join("data", "super_parallel.json")
try:
    print(len(json.load(open(p))))
except Exception:
    print(0)
PYEOF
)

step "6/7 図鑑テーブルを組み立てる"
$PY build_dex.py

step "7/7 整合性を検査"
$PY check_dex.py

echo
echo "=============================================="
echo " できました。 ./run.sh → http://127.0.0.1:8537"
if [ "$SP_N" -lt 40 ]; then
  echo
  echo " !! スーパーパラレル系が $SP_N 件しか入っていない（通常は51件）。"
  echo "    画像が揃ってから  $PY fill_super_parallel.py && $PY build_dex.py"
  echo "    を叩き直すこと。抜けていても図鑑は動くので気づきにくい。"
fi
echo "=============================================="
