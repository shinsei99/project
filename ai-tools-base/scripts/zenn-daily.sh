#!/bin/bash
# 毎晩1本だけ Zenn へ出す（22:00）。
#
# **なぜ1本ずつか**（2026-08-28に判明）:
#   予約投稿（published_at）で25本まとめて push したら、Zenn のレート制限に当たって
#   **24本が丸ごとデプロイされなかった**。Zennのよくある質問より:
#     「記事は**直近24時間以内の投稿数（投稿予約中を含む）**に基づいて判定されます」
#     「上限はさまざまな要素を組み合わせたロジックにより決定され、**非公開**」
#   ＝ 予約もレート制限の対象。まとめて積む使い方はZennの想定と合っていない。
#
#   そこで予約をやめ、**出す晩に1本だけ articles/ へ置いて push する**形にした。
#   published: true のまま置けばデプロイ時にそのまま公開される。1日1本なら上限に当たらない。
#
# 流れ:
#   drafts/zenn_pending/<slug>.md  ←（待機）
#     → 22:00 このスクリプトが1本を articles/ へ移して commit & push
#     → Zenn がデプロイして公開
#     → 22:35 note-daily が「Zennで公開済み」を確認して同じ記事を note へ
#     → 22:45 daily-write が新しい1本を書いて **待機場所へ足す**
#
# 順番は drafts/zenn_order.txt。そこに無いものはファイル名順で後ろ。
#
# 使い方:
#   ./scripts/zenn-daily.sh          1本出す
#   ./scripts/zenn-daily.sh --dry    何を出すか見るだけ
set -u
# launchd から起動されると PATH が空（git / python が見つからない）
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")/.." || exit 1
DRY=""
[ "${1:-}" = "--dry" ] && DRY=1

PEND="drafts/zenn_pending"
[ -d "$PEND" ] || { echo "待機場所が無い: $PEND"; exit 0; }

# ★前に出した1本がまだ公開されていないなら、次を出さない（2026-08-28）。
#   これが無いと、レート制限で弾かれた記事が articles/ に溜まり続け、毎晩1本ずつ
#   「未公開の記事」が増えて、結局また24本まとめてデプロイしようとする状態に戻る。
#   ＝せっかく1本ずつにした意味が無くなる。
STUCK="$(/usr/bin/python3 - <<'PYCHK'
import json, pathlib, urllib.request
# ★ページ送りを最後までたどる。1ページ目だけ見ると、公開が増えたとき
#   「2ページ目にある古い記事」が未公開に見えて毎晩止まってしまう。
live, url = set(), "https://zenn.dev/api/articles?username=shinsei99&order=latest"
try:
    for _ in range(20):                       # 保険（無限ページ送りを踏まない）
        with urllib.request.urlopen(url, timeout=10) as r:
            d = json.load(r)
        live |= {a["slug"] for a in d.get("articles", [])}
        nxt = d.get("next_page")
        if not nxt:
            break
        url = "https://zenn.dev/api/articles?username=shinsei99&order=latest&page=%s" % nxt
except Exception:
    print("")            # Zennを見に行けないときは止めない（従来どおり出す）
    raise SystemExit
stuck = [f.stem for f in sorted(pathlib.Path("../articles").glob("*.md")) if f.stem not in live]
print(" ".join(stuck))
PYCHK
)"
if [ -n "$STUCK" ]; then
  echo "$(date '+%F %T') 前に出した記事がまだZennで公開されていない: $STUCK"
  echo "  次の1本は出さない（未公開を積み増さない）。"
  # ★Zennは上限で弾いた記事を**自動では再試行しない**（ai-tools-base/CLAUDE.md）。
  #   待っているだけでは永久に公開されないので、空コミットを push してデプロイを促す。
  #   上限が解けていればこれで公開される。解けていなければまた弾かれるだけで害は無い。
  if [ -z "$DRY" ]; then
    if ( cd .. && git pull -q --rebase origin main \
         && git commit -q --allow-empty -m "Zenn: 未公開分の再デプロイを促す（$STUCK）" \
         && git push -q origin main ); then
      echo "  空コミットを push した（再デプロイを促した）。上限が解けていれば公開される。"
    else
      echo "  ★空コミットの push に失敗した。"
    fi
  fi
  echo "  デプロイの状況: https://zenn.dev/dashboard/deploys"
  exit 0
fi

NEXT="$(/usr/bin/python3 - <<'PY'
import pathlib
pend = pathlib.Path("drafts/zenn_pending")
order = [x.strip() for x in pathlib.Path("drafts/zenn_order.txt").read_text(encoding="utf-8").splitlines()
         if x.strip() and not x.startswith("#")]
have = {f.stem for f in pend.glob("*.md")}
for s in order:                       # 決めた順を優先
    if s in have:
        print(s); raise SystemExit
rest = sorted(have)                   # 順番表に無いものは名前順で後ろ
print(rest[0] if rest else "")
PY
)"

if [ -z "$NEXT" ]; then
  echo "$(date '+%F %T') 待機中の記事が無い（Zennへ出すものなし）"
  exit 0
fi

echo "$(date '+%F %T') 今夜Zennへ出す: $NEXT"
if [ -n "$DRY" ]; then
  echo "  （--dry なので何もしない。残り $(ls "$PEND"/*.md 2>/dev/null | wc -l | tr -d ' ') 本）"
  exit 0
fi

# ★出す前に関門を通す（個人情報・固有名詞・slugの長さ）。落ちたら出さない
if ! ./publish.sh guard "$NEXT" >/tmp/zenn-daily-guard.txt 2>&1; then
  echo "  ★guard で止まった。今夜は出さない:"; cat /tmp/zenn-daily-guard.txt; exit 1
fi

mv "$PEND/$NEXT.md" "../articles/$NEXT.md" || exit 1
( cd .. && git add -A articles ai-tools-base/drafts/zenn_pending \
  && git commit -q -m "Zenn: $NEXT を公開（毎晩1本・自動）" \
  && git push -q origin main ) || { echo "  ★git に失敗した"; exit 1; }

echo "  push した。Zennのデプロイで公開される。残り $(ls "$PEND"/*.md 2>/dev/null | wc -l | tr -d ' ') 本"
