#!/bin/bash
# 各アプリの依存関係（.venv / node_modules）を作る。**gitで来ないので、PCごとに1回必要。**
#
#   ./dev-setup.sh baikai-generator     # 1本だけ
#   ./dev-setup.sh --all                # 不足している全部（時間がかかる）
#   ./dev-setup.sh --all --dry-run      # 何をするかだけ見る
#
# 失敗しても止まらず次へ進み、最後にまとめて報告する（1本の失敗で全部が止まると使えないため）。
# ログは logs/setup-<アプリ>.log に残る。
#
# ★ 例外が2つある（理由はルート CLAUDE.md）:
#   - chatwork-ai-manager … venv の Python から claude を呼ぶと SIGSEGV で落ちる。
#     **/usr/bin/python3 固定**なので venv を作らず、--target で依存だけ入れる
#   - photo-inpainter … Intel Mac は torch==2.2.2 が最終ビルド。requirements.txt でピン済み
set -uo pipefail
cd "$(dirname "$0")"
mkdir -p logs

DRY=0
TARGETS=()
for a in "$@"; do
  case "$a" in
    --dry-run) DRY=1 ;;
    --all) TARGETS=(--all) ;;
    *) TARGETS+=("$a") ;;
  esac
done
[ ${#TARGETS[@]} -eq 0 ] && { echo "使い方: ./dev-setup.sh <アプリ名> | --all [--dry-run]"; exit 1; }

# venv を作らないアプリ（システムPython固定）
NO_VENV="chatwork-ai-manager keyline"

# venv に使う Python。**新しい方を優先する。**
# システムの /usr/bin/python3 は 3.9 で、3.10以上を要求する依存（streamlit-cropper 等）が入らない。
# ※ chatwork-ai-manager だけは /usr/bin/python3 固定（venv の Python から claude を呼ぶと SIGSEGV）
PYBIN="${PYBIN:-}"
if [ -z "$PYBIN" ]; then
  for c in python3.13 python3.12 python3.11 /usr/bin/python3; do
    if command -v "$c" >/dev/null 2>&1; then PYBIN="$c"; break; fi
  done
fi
echo "venv に使う Python: $PYBIN （$("$PYBIN" -V 2>&1)）"
echo

ok=(); ng=(); skip=()
# bash 3.2 では空配列の ${arr[*]} が unbound になるため、既定値付きで展開する

setup_one() {
  local app="$1"
  [ -d "$app" ] || { echo "  → フォルダが無い: $app"; skip+=("$app(無い)"); return; }
  local log="logs/setup-${app}.log"

  if [ -f "$app/requirements.txt" ]; then
    if [[ " $NO_VENV " == *" $app "* ]]; then
      echo "▶ $app （システムPython固定・venvは作らない）"
      [ $DRY -eq 1 ] && { skip+=("$app(dry)"); return; }
      if /usr/bin/python3 -m pip install --target "$app/.deps" -r "$app/requirements.txt" >"$log" 2>&1; then
        ok+=("$app"); echo "  ✅ .deps に導入（PYTHONPATH=${app}/.deps で使う）"
      else
        ng+=("$app"); echo "  ❌ 失敗 → ${log}"
      fi
      return
    fi
    if [ -d "$app/.venv" ]; then echo "▶ $app  … すでに .venv あり"; skip+=("$app(済)"); return; fi
    echo "▶ $app （Python）"
    [ $DRY -eq 1 ] && { skip+=("$app(dry)"); return; }
    if "$PYBIN" -m venv "$app/.venv" >"$log" 2>&1 &&
       "$app/.venv/bin/pip" install --quiet --upgrade pip >>"$log" 2>&1 &&
       "$app/.venv/bin/pip" install --quiet -r "$app/requirements.txt" >>"$log" 2>&1; then
      ok+=("$app"); echo "  ✅ $(du -sh "$app/.venv" | cut -f1)"
    else
      ng+=("$app"); echo "  ❌ 失敗 → ${log}（末尾: $(tail -1 "${log}" | cut -c1-80)）"
    fi

  elif [ -f "$app/package.json" ]; then
    if [ -d "$app/node_modules" ]; then echo "▶ $app  … すでに node_modules あり"; skip+=("$app(済)"); return; fi
    echo "▶ $app （Node）"
    [ $DRY -eq 1 ] && { skip+=("$app(dry)"); return; }
    if (cd "$app" && npm install --no-audit --no-fund) >"$log" 2>&1; then
      ok+=("$app"); echo "  ✅ $(du -sh "$app/node_modules" | cut -f1)"
    else
      ng+=("$app"); echo "  ❌ 失敗 → ${log}（末尾: $(tail -1 "${log}" | cut -c1-80)）"
    fi

  else
    echo "▶ $app  … 依存不要（静的HTML等）"; skip+=("$app(不要)")
  fi
}

if [ "${TARGETS[0]}" = "--all" ]; then
  # 依存が要るのに未作成のものだけを対象にする
  # macOS の bash 3.2 には mapfile が無いので while-read で組む
  list=()
  while IFS= read -r app; do
    [ -n "$app" ] && list+=("$app")
  done < <(
    for d in */; do
      app="${d%/}"
      # NO_VENV のアプリは .venv を見ない（=$NO_VENV との単純比較は複数入ったとたん
      # 効かなくなるので、空白区切りの部分一致で判定する）。
      # ★`pip install --user` で system python に入っている場合も「済み」とみなす
      #   （メインPCの chatwork-ai-manager / keyline は実際この形。dev-doctor の
      #    ok(sys) 判定と揃える。ここを揃えないと毎回「未導入」に見えて入れ直してしまう）
      if [[ " $NO_VENV " == *" $app "* ]]; then
        [ -f "$app/requirements.txt" ] || continue
        [ -d "$app/.deps" ] && continue
        first=$(grep -v '^\s*#' "$app/requirements.txt" | grep -v '^\s*$' | head -1 |
                sed -E 's/[][<>=!;].*//' | tr '-' '_' | tr -d ' ')
        /usr/bin/python3 -c "import ${first}" 2>/dev/null || echo "$app"
      elif [ -f "$app/requirements.txt" ] && [ ! -d "$app/.venv" ]; then
        echo "$app"
      fi
      if [ -f "$app/package.json" ] && [ ! -d "$app/node_modules" ]; then echo "$app"; fi
    done | sort -u
  )
  echo "対象 ${#list[@]}本: ${list[*]:-なし}"
  echo
  for app in ${list[@]+"${list[@]}"}; do setup_one "$app"; done
else
  for app in ${TARGETS[@]+"${TARGETS[@]}"}; do setup_one "$app"; done
fi

echo
echo "──────── 結果 ────────"
echo "成功 ${#ok[@]}: ${ok[*]:-なし}"
echo "失敗 ${#ng[@]}: ${ng[*]:-なし}"
echo "対象外 ${#skip[@]}: ${skip[*]:-なし}"
[ ${#ng[@]} -gt 0 ] && echo "※ 失敗したものは logs/setup-<アプリ>.log を見る"
python3 dev-doctor.py >/dev/null 2>&1 && echo "状態確認: python3 dev-doctor.py"
exit 0
