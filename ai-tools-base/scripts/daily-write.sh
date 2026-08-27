#!/bin/bash
# 毎日1本、新しいネタから記事を書いて、公開の予約まで入れる。
#
#   ./scripts/daily-write.sh          1本書いて、guard を通れば予約に入れる
#   ./scripts/daily-write.sh --dry    書くところまで。予約には入れない
#
# 流れ:
#   ① scan          … まだ書いていないネタを拾う（書いたものは .neta_used.txt で除外）
#   ② claude -p     … その中から1つ選び、根拠を実物で確認して3媒体の原稿を書く
#   ③ guard         … ★個人情報・固有名詞・寿命を縮める語を機械で止める
#   ④ zenn-schedule … 通ったものだけ、毎日22:30の予約に入る
#   ④-b links       … 昨夜までに公開された Zenn / note のURLを本体の links へ入れる
#   ⑤ site          … 本体サイトを本番へ（Zennはpushで出るが、本体は vercel --prod が要る）
#
# ★③を通らなければ、その日は何も出ない。それが安全側。ログを見て人が直す。
#
# **なぜ毎日か**（2026-08-27 に週次から変更）: Zenn も note も「毎日1本」出す設定なので、
# 書くのが週1本だと予約が尽きて出せなくなる。書く速さと出す速さを揃えると、
# 予約の残りが一定（25日ぶん）に保たれて途切れない。
#
# **なぜ 22:45 か**: 22:30 Zenn公開 → 22:35 note投稿 の直後だから。その晩に出たURLを
# ④-b で links に入れて、そのまま⑤で本番へ出せる（朝に置くと約10時間ずれる）。
# あわせて、**Macが起きていないといけない時間帯が夜の1回だけ**になる。
set -u
cd "$(dirname "$0")/.."
DRY=""
[ "${1:-}" = "--dry" ] && DRY="1"

echo "=================================================="
echo "  $(date '+%Y-%m-%d %H:%M')  daily-write"
echo "=================================================="

# ① 新しいネタ
NETA="$(/usr/bin/python3 scripts/neta_scan.py 2>&1)"
echo "$NETA"
if echo "$NETA" | grep -q "新しいものは無い"; then
  echo "→ 書くものが無いので終わり"
  exit 0
fi

# ★claude は絶対パスで呼ぶ（2026-08-28）。
#   このMacには claude が2つある:
#     /usr/local/bin/claude    … 6月のnpm版。**native binary 未導入で壊れている**
#     /opt/homebrew/bin/claude … Homebrew版。正常（2.1.226）
#   PATH は /usr/local/bin が先なので、裸で `claude` と書くと**壊れたほうを掴む**。
#   毎晩22:45にここで失敗し、ネタ収集まではできているのに記事が1本も書けていなかった。
CLAUDE_BIN="${CLAUDE_BIN:-/opt/homebrew/bin/claude}"
if [ ! -x "$CLAUDE_BIN" ]; then
  CLAUDE_BIN="$(command -v claude)" || { echo "claude が見つかりません"; exit 1; }
fi

# ② 書かせる。**破壊的な操作はさせない**ので、許可するツールを絞る
BEFORE="$(ls content/works/*.json | wc -l | tr -d ' ')"
BEFORE_ART="$(ls ../articles/*.md 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' | sort)"
OUT="$("$CLAUDE_BIN" -p "$(cat <<PROMPT
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
- **既にある記事と同じ話を書かない。** content/works/ を見て、同じ症状・同じ原因の記録が
  既にあるなら、そのネタは選ばずに別のものにする

最後に次の4行だけを出力してください（他は書かない）。
  1〜3行目: 作った3つのファイルのパス
  4行目: NETA: <選んだネタの1行をそのまま貼る>
PROMPT
)" --allowedTools "Read,Grep,Glob,Write,Edit,Bash(git log:*),Bash(git show:*),Bash(ls:*),Bash(cat:*),Bash(sed:*),Bash(grep:*),Bash(wc:*)" 2>&1)"
echo "$OUT" | tail -25

AFTER="$(ls content/works/*.json | wc -l | tr -d ' ')"
if [ "$BEFORE" = "$AFTER" ]; then
  echo "→ 記事が増えていない。今日は見送り"
  exit 0
fi

# ★書いた記事を drafts/zenn_order.txt の末尾へ足す。
# Zenn の予約も note の投稿順も、この並びを見て「載っていないものは名前順で後ろ」に回す。
# **載せないと、Zennは書いた順・noteはアルファベット順**になり、同じ日に別の記事が出る
# （noteの本文にはZennのURLが埋めてあるので、噛み合わないとリンク先がまだ無い状態になる）。
AFTER_ART="$(ls ../articles/*.md 2>/dev/null | xargs -n1 basename 2>/dev/null | sed 's/\.md$//' | sort)"
NEW_ART="$(comm -13 <(echo "$BEFORE_ART") <(echo "$AFTER_ART"))"
for s in $NEW_ART; do
  if ! grep -qx "$s" drafts/zenn_order.txt 2>/dev/null; then
    echo "$s" >> drafts/zenn_order.txt
    echo "zenn_order.txt の末尾に足した: $s"
  fi
done

# 書いたネタを記録する。**これが無いと同じネタを毎日書く**（日次にした以上ここが要）
CHOSEN="$(echo "$OUT" | grep '^NETA: ' | tail -1 | sed 's/^NETA: //')"
if [ -n "$CHOSEN" ]; then
  /usr/bin/python3 scripts/neta_scan.py --used "$CHOSEN"
else
  echo "★選んだネタを報告してこなかった。重複よけが効かないので、ログを見て"
  echo "  ./publish.sh scan --used \"<書いたネタの1行>\" を人が入れること"
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

  # 昨夜までに公開された Zenn / note のURLを本体の links へ入れる。
  # **本体・Zenn・note の3点で1本**なので、ここが埋まるまでが1本（validate の転載⚠️が消える）。
  # 毎晩1本出るようになった以上、手で足すと毎日の作業になるため機械にした。
  echo "--- 転載URLを links へ ---"
  /usr/bin/python3 scripts/links_sync.py --write

  ( cd .. && git add -A articles ai-tools-base && \
    git commit -q -m "日次: 記事を1本足して予約に入れた（自動）" && git push -q origin main ) \
    && echo "push した"

  # ⑤ 本体サイトを本番へ。**Zennはpushで出るが、本体は vercel --prod が要る**ので
  #    ここに入れないと本体だけ毎日置いていかれる（2026-08-27 オーナー判断で自動化）。
  #    ③の guard を通ったときだけここに来る＝落ちた日はデプロイもしない。
  echo "--- 本体サイトを本番へ ---"
  ./publish.sh site || echo "★デプロイに失敗した。記事は push 済みなので ./publish.sh site を人が叩くこと"
fi
echo "=== 終わり $(date '+%H:%M') ==="
