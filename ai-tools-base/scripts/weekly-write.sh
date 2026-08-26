#!/bin/bash
# 週に一度、新しいネタから記事を1本書いて、公開の予約まで入れる。
#
#   ./scripts/weekly-write.sh          1本書いて、guard を通れば予約に入れる
#   ./scripts/weekly-write.sh --dry    書くところまで。予約には入れない
#
# 流れ:
#   ① scan          … 前回以降に SESSION_LOG へ書かれたネタを拾う
#   ② claude -p     … その中から1つ選び、根拠を実物で確認して3媒体の原稿を書く
#   ③ guard         … ★個人情報・固有名詞・寿命を縮める語を機械で止める
#   ④ zenn-schedule … 通ったものだけ、毎日22:30の予約に入る
#
# ★③を通らなければ、その週は何も出ない。それが安全側。ログを見て人が直す。
set -u
cd "$(dirname "$0")/.."
DRY=""
[ "${1:-}" = "--dry" ] && DRY="1"

echo "=================================================="
echo "  $(date '+%Y-%m-%d %H:%M')  weekly-write"
echo "=================================================="

# ① 新しいネタ
NETA="$(/usr/bin/python3 scripts/neta_scan.py 2>&1)"
echo "$NETA"
if echo "$NETA" | grep -q "新しいものは無い"; then
  echo "→ 書くものが無いので終わり"
  exit 0
fi

# ② 書かせる。**破壊的な操作はさせない**ので、許可するツールを絞る
BEFORE="$(ls content/works/*.json | wc -l | tr -d ' ')"
claude -p "$(cat <<PROMPT
あなたは ~/ai-tools-base の「制作記録」を書く担当です。**1本だけ**書いてください。

## 選ぶ
次はこのリポジトリの SESSION_LOG から拾った、まだ記事にしていないネタです。

$NETA

この中から、**記事にする値打ちがあるもの**を1つ選んでください。
選ばないもの: 具体的なモデル名やSDKのバージョンに依存する話 / スマホやブラウザ固有の細かい制限 /
不動産の仕事から遠いもの（カード図鑑・メール保管など）。

## 裏を取る
**思い出しで書かないでください。** 根拠になるコミットやファイルを実際に開いて、
症状・原因・直し方・数値を確認します。**確認できなかった数値は書かない**（metric を省く）。

## 書く（3つ）
1. content/works/<slug>.json … 既存のファイルと同じ形。category は realestate/tool/game/media、
   visibility は public。summary は10〜200字。improvements に 症状/原因/直し方 を入れる
2. ../articles/<slug>.md … Zenn用。frontmatter は title/emoji/type/topics/published: false。
   **published_at は書かない**（予約は別の道具が振ります）。コード例を入れて技術者向けに
3. drafts/note/<slug>.md … note用。**表は使えないので箇条書き**にする。非技術者にも分かる書き方で、
   末尾に https://zenn.dev/shinsei99/articles/<slug> を置く

## 絶対に守ること
- **固有名詞を書かない**（会社名・物件名・人名・住所・電話番号）。すべて一般化する
- 数値は**実測値だけ**。例示の電話番号を使うときは 03-5555-xxxx 帯にする
- 書き終えたら、drafts/NETA.md にその行があれば消す

最後に、作った3つのファイル名だけを1行ずつ出力してください。
PROMPT
)" --allowedTools "Read,Grep,Glob,Write,Edit,Bash(git log:*),Bash(git show:*),Bash(ls:*),Bash(cat:*),Bash(sed:*),Bash(grep:*),Bash(wc:*)" 2>&1 | tail -25

AFTER="$(ls content/works/*.json | wc -l | tr -d ' ')"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "→ 記事が増えていない。今週は見送り"
  exit 0
fi

# ③ 関門
echo "--- guard ---"
if ! /usr/bin/python3 scripts/guard.py; then
  echo "★guard で止まった。**公開しない**。原稿を直してから ./publish.sh zenn-schedule --write"
  exit 1
fi

# ④ 予約（既に予約済み・公開済みのものには触らない）
if [ -n "$DRY" ]; then
  echo "--- dry: 予約には入れない ---"
  /usr/bin/python3 scripts/zenn_schedule.py
else
  echo "--- 予約に入れる ---"
  /usr/bin/python3 scripts/zenn_schedule.py --write
  ( cd .. && git add -A articles ai-tools-base && \
    git commit -q -m "週次: 記事を1本足して予約に入れた（自動）" && git push -q origin main ) \
    && echo "push した"
fi
echo "=== 終わり $(date '+%H:%M') ==="
