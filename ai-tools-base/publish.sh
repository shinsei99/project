#!/bin/bash
# AIツールベース — 3媒体（本体サイト / Zenn / note）を1か所から更新する。
#
#   ./publish.sh status          いま3媒体がどうなっているかを表示（まずこれ）
#   ./publish.sh site            本体サイトを本番へデプロイ（Vercel・手動デプロイ）
#   ./publish.sh zenn            articles/ を push して Zenn へ反映
#   ./publish.sh note <名前>     note 用のHTMLをクリップボードへ（本文欄で ⌘V）
#
# 前提（1回だけ・対話が要る）:
#   npx vercel login   … ブラウザが開く。所有者は daikyocorps-3085
#   npx vercel link    … team: brain-dump / project: ai-tools-base を選ぶ
#   ブラウザで zenn.dev と note.com にログインしておく
set -u
cd "$(dirname "$0")"

REPO_ROOT="$(cd .. && pwd)"
ARTICLES="$REPO_ROOT/articles"
SITE_URL="https://ai-tools-base.vercel.app"
ZENN_USER="shinsei99"

zenn_published_slugs() {
  curl -s "https://zenn.dev/api/articles?username=$ZENN_USER&order=latest" \
    | /usr/bin/python3 -c "import sys,json;print('\n'.join(a['slug'] for a in json.load(sys.stdin).get('articles',[])))"
}

case "${1:-status}" in

  status)
    echo "── 本体サイト ──────────────────────────────"
    printf '  %s → HTTP %s\n' "$SITE_URL" \
      "$(curl -s -o /dev/null -w '%{http_code}' --max-time 10 "$SITE_URL/")"
    if [ -d .vercel ]; then echo "  Vercel: リンク済み"; else
      echo "  Vercel: **未リンク**（npx vercel login → npx vercel link が要る）"; fi

    echo "── Zenn ────────────────────────────────────"
    pub="$(zenn_published_slugs)"
    for f in "$ARTICLES"/*.md; do
      s="$(basename "$f" .md)"
      if grep -q '^published: true' "$f"; then
        if echo "$pub" | grep -qx "$s"; then echo "  ✅ $s"
        else echo "  ⬜ $s … published:true なのに未反映（投稿数の上限。空けて再push）"; fi
      else
        echo "  －  $s（published:false）"
      fi
    done

    echo "── note ────────────────────────────────────"
    echo "  原稿: $(ls drafts/note/*.md 2>/dev/null | wc -l | tr -d ' ') 本"
    echo "  貼り付けは ./publish.sh note <名前>（Markdownは効かないのでHTMLで貼る）"
    ;;

  site)
    # 出力を捨てないこと。最後に Aliased … が出るのを目で見る（過去に握りつぶして
    # デプロイできていないのに成功と誤認した）
    npm run validate || { echo "validate で止まった。直してから再実行"; exit 1; }
    npx vercel --prod
    echo "--- 反映確認 ---"
    sleep 5
    curl -s -o /dev/null -w "$SITE_URL → HTTP %{http_code}\n" --max-time 15 "$SITE_URL/"
    ;;

  zenn)
    # Zenn は GitHub 連携。リポジトリ直下 articles/ を push すれば反映される。
    # ⚠️ 直近24時間の投稿数に上限があり、超えたぶんは**黙って**デプロイされない。
    #    時間を空けて **もう一度 push** が要る（空pushでよい）。
    before="$(zenn_published_slugs | wc -l | tr -d ' ')"
    ( cd "$REPO_ROOT" && git add articles && git commit -m "Zenn: 記事を更新" || true; git push origin main )
    echo "push 済み。反映まで数分かかる。1〜2分後に ./publish.sh status で確認すること"
    echo "（push前の公開数: ${before}）"
    ;;

  note)
    name="${2:-}"
    if [ -z "$name" ]; then
      echo "使い方: ./publish.sh note <名前>"; ls drafts/note/*.md | xargs -n1 basename | sed 's/\.md$//' | sed 's/^/  /'
      exit 1
    fi
    /usr/bin/python3 drafts/note/md2html.py "$name"
    echo "note の本文欄で ⌘V。見出し画像は「記事にあう画像を選ぶ」が速い"
    ;;

  *)
    sed -n '2,14p' "$0"
    ;;
esac
