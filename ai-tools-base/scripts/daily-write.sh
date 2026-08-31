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
#   ④ 待機場所へ   … 通ったものだけ drafts/zenn_pending/ へ。Zennへは 22:00 に1本ずつ
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

# ★launchd から起動されると PATH が空になり、claude CLI の終了フック（Vercelプラグインの
#   session-end-cleanup.mjs）が呼ぶ node が見つからず、**claude が毎回エラー終了する**。
#   2026-08-28未明のOCR全滅・翻訳940通全滅はこれが原因だった（定額枠切れではない）。
#   手で流すと PATH があるので再現しない＝気づきにくい。[[reference_launchd_path_node]]
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
cd "$(dirname "$0")/.."
DRY=""
[ "${1:-}" = "--dry" ] && DRY="1"

echo "=================================================="
echo "  $(date '+%Y-%m-%d %H:%M')  daily-write"
echo "=================================================="

# ★節約モード中は書かない（2026-08-31 オーナー指示「枠が少ない」）。
#   記事を1本書くのは claude の消費が大きい工程。しかも**いま書いても出せない**:
#   待機（zenn_pending）に29本の在庫があり、Zennは投稿数の上限で止まっている。
#   印を消せば翌晩から自動で再開する（launchd は外さない＝戻し忘れない）。
if [ -f "$HOME/.ai-quota-saver" ]; then
  echo "節約モード中のため、今夜は記事を書きません（在庫があるので困らない）"
  echo "  戻すには: ~/ai-quota-saver.sh off"
  exit 0
fi

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
  echo "★guard で止まった。**公開しない**。原稿を直すこと（待機場所にも入らない）"
  exit 1
fi

# ④ 書いた記事は **待機場所へ置く**（2026-08-28 に予約投稿をやめた）。
#   Zenn は「直近24時間の投稿数（**予約中を含む**）」でレート制限をかける。
#   25本まとめて予約したら24本が丸ごとデプロイされなかった（実際に発生）。
#   いまは 22:00 の zenn-daily.sh が待機場所から1本ずつ出す。
if [ -n "$DRY" ]; then
  echo "--- dry: 待機場所には入れない ---"
else
  # ★書いた記事を待機場所へ移す（2026-08-31 に復活させた）。
  #
  #   8/29 に「Zennで未公開の記事を articles/ から引き戻す処理」を消したとき、
  #   **待機場所へ入れる処理まで一緒に消えていた**。以来、書いた記事は
  #   `published: false` のまま articles/ に残り続けていた。
  #   zenn-daily は **drafts/zenn_pending からしか選ばない**ので、
  #   articles/ に残った記事は順番表に載っていても**永久に出ない**。
  #   実際 search-fallback-fills-topk と name-substitution-misfires の2本が
  #   取り残されていた（8/31に手で待機場所へ戻した）。
  #
  #   ここで `published: true` にしておく（待機場所の他の記事と同じ形）。
  #   zenn-daily は出す晩にファイルを articles/ へ移すだけなので、
  #   false のまま入れると移動しても Zenn が公開しない。
  PEND="drafts/zenn_pending"
  mkdir -p "$PEND"
  for s in $NEW_ART; do
    [ -f "../articles/$s.md" ] || continue
    if [ -e "$PEND/$s.md" ]; then
      echo "★待機場所に同名がある。移さない: $s"; continue
    fi
    /usr/bin/python3 - "../articles/$s.md" "$PEND/$s.md" <<'PYMOVE'
import pathlib, sys
src, dst = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
t = src.read_text(encoding="utf-8")
dst.write_text(t.replace("published: false", "published: true", 1), encoding="utf-8")
src.unlink()
PYMOVE
    echo "待機場所へ入れた: $s（Zennへは 22:00 に1本ずつ）"
  done

  echo "--- 待機場所の状況（Zennへは 22:00 に1本ずつ出る） ---"
  # ★ここで articles/ から記事を引き戻してはいけない（2026-08-29に直した）。
  #
  #   もとは「Zennで未公開の記事を待機場所へ戻す」処理だった。だが 22:00 の zenn-daily が
  #   出したばかりの1本は、**45分後のこの時点ではまだ Zenn が公開していない**のが普通で、
  #   毎晩それを引き戻していた。翌 22:00 には zenn-daily が「前に出した記事がまだ公開
  #   されていない」と言って次を出さない。**結果、Zennへ1本も出ない状態が続いていた**
  #   （8/27に仕組みを入れてから公開ゼロ／待機26本）。
  #
  #   引き戻しは、予約投稿をやめて待機場所方式へ移した**一度きりの引っ越し**のための処理で、
  #   移行が済んだ今は害しかない。articles/ に未公開が溜まる心配も要らない
  #   ——zenn-daily 自身が「未公開が1本でもあれば次を出さない」ので、最大でも1本しか増えない。
  /usr/bin/python3 - <<'PYSTAT'
import pathlib, json, urllib.request
REPO = pathlib.Path(".."); PEND = pathlib.Path("drafts/zenn_pending")
PEND.mkdir(parents=True, exist_ok=True)
try:
    with urllib.request.urlopen(
            "https://zenn.dev/api/articles?username=shinsei99&order=latest", timeout=10) as r:
        live = {a["slug"] for a in json.load(r).get("articles", [])}
except Exception:
    live = None
waiting = len(list(PEND.glob("*.md")))
if live is None:
    print("  待機中 %d 本（Zennを見に行けなかったので公開状況は不明）" % waiting)
else:
    inflight = [f.stem for f in sorted((REPO / "articles").glob("*.md")) if f.stem not in live]
    print("  待機中 %d 本 / Zenn公開済み %d 本" % (waiting, len(live)))
    if inflight:
        print("  出したがまだZennで公開されていない: %s" % " ".join(inflight))
        print("  → 引き戻さずそのまま置く。Zennのデプロイで公開される。"
              "翌日も公開されないままなら zenn-daily が空コミットで再デプロイを促す")
PYSTAT

  # 昨夜までに公開された Zenn / note のURLを本体の links へ入れる。
  # **本体・Zenn・note の3点で1本**なので、ここが埋まるまでが1本（validate の転載⚠️が消える）。
  # 毎晩1本出るようになった以上、手で足すと毎日の作業になるため機械にした。
  echo "--- 転載URLを links へ ---"
  /usr/bin/python3 scripts/links_sync.py --write

  # ★専用インデックスでコミットする（2026-08-29 に方式を確定）。
  #   このMacは複数セッションが同じ作業ツリーを同時に触る。共有インデックス（.git/index）を
  #   使うと、他人のステージを引き継いだり index.lock とぶつかったりする。
  #   2026-08-28 に素の commit で31ファイルを消し、その復旧コミットもさらに巻き込んだ。
  #   `git read-tree HEAD` で毎回まっさらから始めれば、共有インデックスに一切触らない。
  ( export GIT_INDEX_FILE="$(mktemp -t dailywrite-index)"; \
    cd .. \
    && git read-tree HEAD \
    && git add -A -- articles ai-tools-base \
    && git commit -q -m "日次: 記事を1本足して待機場所へ入れた（自動）" \
    && { git push -q origin main \
         || { echo "  push が弾かれた。取り込み直して押し直す"; \
              git fetch -q origin main && git rebase -q --autostash origin/main \
              && git push -q origin main || { git rebase --abort 2>/dev/null; false; }; }; }; \
    rc=$?; rm -f "$GIT_INDEX_FILE"; exit $rc ) \
    && echo "push した"

  # ⑤ 本体サイトを本番へ。**Zennはpushで出るが、本体は vercel --prod が要る**ので
  #    ここに入れないと本体だけ毎日置いていかれる（2026-08-27 オーナー判断で自動化）。
  #    ③の guard を通ったときだけここに来る＝落ちた日はデプロイもしない。
  echo "--- 本体サイトを本番へ ---"
  ./publish.sh site || echo "★デプロイに失敗した。記事は push 済みなので ./publish.sh site を人が叩くこと"
fi
echo "=== 終わり $(date '+%H:%M') ==="
