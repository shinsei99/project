## 2026-08-27（メインPC）— サブPCの引き継ぎを受領。自動化2本を常駐に入れた

### 完了したこと
- **`drafts/.pii-blocklist.txt` をメインPCで作成**（gitignoreなのでサブPCからは渡らない）。
  出所は `parking-map/serve.py` と `gyomu-manual/業務マニュアル.html`。
  **会社11・物件28・地番1・人29＝69語**。`./publish.sh guard` で **85本すべて問題なし＝誤検知0**
  - **ありふれた姓（佐藤・中村・鈴木・青木）は意図的に外した**。技術記事の例示文で誤爆すると
    記事が理由なく止まるため（8/27にサブPCで一般語を入れて記事4本が止まった件と同じ失敗を避ける）
  - サブPCの実物は51件なので**中身は一致していない**。厳密に揃えるならファイルを手で運ぶ
- **本体サイトを本番へ反映**（`./publish.sh site`）。`ai-tools-base-d8p29cszx` が READY。
  **公開41本すべてが本番にある**ことを1本ずつ HTTP で確認、`/novel` も 200
- **weekly-write を常駐に入れた**（`com.shinsei.weekly-write`・日曜8:07）。次回は 8/30(日)
- **note-daily を常駐に入れた**（`com.shinsei.note-daily`・毎日22:35）。
  `--login` で `~/.note-profile` を作り、`--check` が **「OK（エディタを開けている）」**

### 発生したエラーと解決策
- **本番反映後も3本が404のまま**（`pokecard-dex` / `psa-collection` / `swim-tracker`）→
  原因: **`visibility: "internal"` の意図的な非公開**。デプロイ漏れではない。
  以後、未反映の確認は `visibility` を見てから判断すること
- **macOS の zsh に `timeout` が無い**（`command not found`）。検証コマンドに使わない

### 次回への引き継ぎ事項・未解決の課題
- **今夜22:35に note の1本目**（`deploy-not-reflected`）。**翌朝 `/tmp/note-daily.log` と
  `./publish.sh status` を見ること**。画面ありで動くので、スリープ・ログアウト中は動かない
- **note を1本出したら、URLを `content/works/<slug>.json` の `links` に追記 → `./publish.sh site`**
- **サブPCの launchd には入れない**（投稿記録は端末ごと。2台で動かすと同じ記事が2本出る）

## 2026-08-27（続き・サブPC）— 投稿と執筆を自動化した

### 完了したこと
- **note の自動投稿**（`scripts/note_post.py` / `note-daily.sh` / launchd 22:35）。
  Playwright ＋ **ログイン済みプロファイル**（`~/.note-profile`）
- **週次の自動執筆**（`scripts/weekly-write.sh` / launchd 日曜8:07）。
  scan → `claude -p` が1本書く → guard → 予約、まで自動
- **公開前の関門 `./publish.sh guard`**。個人情報の型／禁止語リスト／固有名詞らしきもの／
  寿命を縮める語を機械で止める。**落ちたら公開しない**
- **`./publish.sh scan`**。各アプリの SESSION_LOG から、まだ書いていないネタを拾う（実測111件）
- **計測**: 本体に Vercel Analytics、`scripts/zenn_stats.py`（ZennのPV）、`note_status.py`
- 本体サイトを本番反映（制作記録41本＋索引＋`/novel`）。**Zenn 25本を 8/27〜9/20 に予約**

### 発生したエラーと解決策
- **`claude -p`（非対話）からは claude-in-chrome の拡張が使えない**（「接続されているブラウザ系MCPは
  playwright のみ」）→ 自前で Playwright を使う
- **note のエディタは headless では描画されない**（`editor.note.com/new` で止まり body が空）→
  **画面ありで動かし、ウィンドウを画面の外**（`--window-position=-3000,-3000`）へ
- **`--login` のループが人の画面を奪っていた**（3秒ごとに `goto` していた）→ 確認は**別タブ**で行う
- **guard の初回検査で、実在の住所と電話番号が記事に入っていた**（`normalize-japanese-data`）→
  住所は番地だけに、電話は例示用の 5555 帯へ。**関門が実際に仕事をした1件**
- guard の誤検知を潰した: 「ビル**ド**」を建物名、`claude-code` をモデル名、電話番号の一部を郵便番号
- **禁止語リストに一般語を入れて記事4本が止まった**（自社ビル・技術記事）→ 一般語は入れない
- **予約日が既存と重なっていた**（開始日から順に振るだけだった）→ 埋まっている日を飛ばす
- **`zenn_order.txt` に無い記事が note だけ永久に出ない**状態だった → 無いものは後ろに付ける

### 次回への引き継ぎ事項・未解決の課題
- **メインPCで launchd を2つ入れる**（note-daily / weekly-write）。手順は直下 `TODO.md` の先頭
- **`.pii-blocklist.txt` は gitignore なのでメインPCには渡らない。** あちらでも作ること
  （サブPCは実語51件＝会社5・物件42・地番3・人1）
- **サブPCでは常駐させない**（投稿記録は端末ごと。2台で動かすと二重投稿）
- **画面ありで動くので、スリープ・ログアウト中は動かない可能性**がある。翌朝ログを見る
- note の下書き2本（検証で作ったもの）はオーナーが削除済み

## 2026-08-27（サブPC）

### 完了したこと
- **ネタ帳の在庫66本を、26本の記事に束ねて全部書き上げた**（前日からの続き）。
  3媒体（不動産）**22本**＝本体JSON＋Zenn原稿＋note原稿／本体のみ（ツール・メディア）**4本**。
  制作記録は 14本 → **40本**（不動産33）。`drafts/NETA.md` は在庫0で締め、
  以後は新しく起きたことを足す台帳として残した。束ね方と状態は `drafts/PLAN.md`
- **Zenn に22本の予約投稿を入れて push した**（**2026-08-27〜09-17 の毎日22:30**・1日1本）。
  公開順は `drafts/zenn_order.txt`（同じ系統が続かないように並べた）
- **小説（続編）への導線をサイトに置いた** — `content/novel.json` ＋ `/novel` ＋
  制作記録の詳細に「この記録は、小説の題材になっています」＋フッター（全ページ）。
  続編は未投稿なので行き先は `/novel`。**カクヨムに出したら `novel.json` の `url` を入れるだけ**で
  フッターも詳細ページも作品ページへ直接飛ぶ。対応は12話ぶん（10・12・14・15・17・19話ほか）
- **note の1本目を下書きまで入れた**（`直したはずのものが、直っていなかった`＝8/27ぶん）。**未公開**

### 発生したエラーと解決策
- **`./publish.sh status` が、予約中の22本を「投稿数の上限」と誤表示した** → 原因: **予約中の記事は
  Zenn の公開APIに出ない**ので、公開済みと区別できていなかった → `scripts/zenn_status.py` を作り、
  `published_at` を見て 公開済み／予約中／下書き／要確認 を出す形にした
- **note は表を扱えない**（`md2html` も Markdown の表に未対応で、1段落に潰れる）→ 原稿側を箇条書きに直した
  （該当は `deploy-not-reflected` の1本だけ。他21本に表は無い）
- **note の予約投稿は「プレミアム」（月500円・加入月無料）** → 公開設定の詳細設定で確認。
  無料のままでは日時指定ができない
- **Chrome の拡張が2つ接続されていた**（両方このMac＝別プロファイル）。`Browser 1`
  （deviceId `a7dc39a3-bdb4-4492-9e28-ea47a247ee39`）が note にログイン済みの側だった

### 次回への引き継ぎ事項・未解決の課題
- ★**本体サイトが未デプロイ**。制作記録26本も `/novel` も**本番に出ていない**（`/works/kana-name-matching` が404）。
  `./publish.sh site` で反映する（**サブPCからでも可**。`npx vercel --prod --scope brain-dump`）。
  **Zenn の1本目が 8/27 22:30 に出る**ので、その前に出しておくのが望ましい
- ★**note 22本の出し方が未決**。①プレミアム加入（加入月無料・22日ぶんなのでお試し期間で終わる）→
  私が22本すべてに日時を振れる ②毎晩ひと言もらって1本ずつ投稿 ③launchd で自動化（**拡張が繋がるか未検証**）。
  **Claude のセッション内 cron は7日で失効しセッションを閉じると消えるので、22日間には使えない**
- note を出したら、**URLを `content/works/*.json` の `links` に追記 → `./publish.sh site`**。
  `npm run validate` の転載⚠️が消えれば1本完了

## 2026-08-26（サブPC）

### 完了したこと
- **ネタ帳の在庫と3媒体の進み具合を1画面で出す `./publish.sh queue` を作った**（`scripts/queue.py`）。
  在庫の台帳は **`drafts/NETA.md` 一本のまま**にして、そこをパースする形にした
  （書き写して二つ持つと必ず食い違う、というのはこの媒体で何度も書いてきた話なので）。
  いまの数字: 本体14本（不動産11）／Zenn 11／note 11 で3媒体は揃っている。
  **在庫は64本（3媒体に出せる〔不動産〕50・本体のみ14）**。章別の残りと「次に書く候補」も出る
- **Zenn の予約投稿を振る `./publish.sh zenn-schedule` を作った**（`scripts/zenn_schedule.py`）。
  未公開の記事に **毎日22:30** の `published_at` を1日ずつ振る。既定はドライラン、`--write` で書き込み、
  **push はしない**（外へ出すのは人の操作）
- 方針を決めた: **本体サイトとnoteは在庫を全部書く。Zennだけ毎日1本ずつ後追いで公開する**

### 発生したエラーと解決策
- **Zenn の公開日時は一度設定すると変更できない**（公式の Zenn CLI ガイドに明記。やらかし報告記事もある）
  → `zenn_schedule.py` は **すでに `published_at` がある記事と、Zenn API に出ている公開済みの記事には触らない**。
  さらに既定をドライランにして、日付を目で見てから `--write` する形にした
- Zenn の予約投稿の書式は `published: true` ＋ `published_at: YYYY-MM-DD hh:mm`（JST）。
  **`published: false` のままだと時刻が来ても公開されない**

### 次回への引き継ぎ事項・未解決の課題
- **在庫50本（不動産）の本体＋note を順に書く**のが次の作業。`./publish.sh queue` が候補を出す
- **予約投稿とレート制限の関係は未確認**。Zenn は直近24時間の投稿数に上限があり、超えた分は黙って
  反映されない。予約を大量に push したときに引っかかるかは**実測していない** →
  最初は数本ずつ push して `./publish.sh status` で反映を見ること
- **カクヨムへの誘導は保留**（続編が未投稿のため。オーナー判断 2026-08-26）。
  作りかけの対応データは `drafts/novel/novel-links.json` に退避してある
  （小説32話のうち、**公開済みの制作記録と結びつくのは9話**／ネタ帳の在庫まで含めると18話）

## 2026-08-25（サブPC・夜）— 11本目の3点セットを、このPCから3媒体とも公開した

### 完了したこと

- **11本目「3枚目から必ず失敗する。スマホで撮った書類は、送信の上限に当たっていた」を3媒体とも公開**
  （題材はネタ帳42番＝`shorui-mobile` の iOS Safari × Vercel。裏取りは commit
  `7eeec42` / `30526bd` / `5b1285b` / `f4d724d` と現行 `app/page.tsx` を読んで実施）
  - 本体 https://ai-tools-base.vercel.app/works/mobile-photo-upload （21:3x）
  - Zenn https://zenn.dev/shinsei99/articles/ios-safari-vercel-upload-413 （22:1x・再push で反映）
  - note https://note.com/shinsei99/n/nc4ce3a25341d （21:5x・拡張から自動投稿。h2×6・p×47・a×3・2,335文字。
    見出し画像＝みんなのフォトギャラリー「書類の山に埋もれる男性」Photo by alkalinedrysell）
- `links` を追記して再デプロイ。**本番ページから Zenn / note の両リンクが引けることを確認**。
  `npm run validate` の転載⚠️は 0 件（残る4件は tools の review 空欄で別件）
- 記事の中身: ①iOS Safari は FormData のファイル名に非ASCIIが混ざると例外
  ②Vercel のボディ上限 4.5MB（写真1枚2〜4MB＝3枚目で必ず超える）
  ③`createImageBitmap` が iOS Safari で失敗し `catch` が原本を返すので縮小が黙って無効になる
  ④縮小は対症療法なので 1枚＝1リクエストに分割し、束IDで1フォルダに集約

### 発生したエラーと解決策

- **症状**: push しても Zenn に出ない（`./publish.sh status` が ⬜）。
  **原因**: **投稿数の上限**。デプロイ履歴のお知らせ欄に
  「次の記事は投稿数の上限に達したためデプロイされませんでした: ios-safari-vercel-upload-413」。
  前回公開（10本目）が 8/24 22:08 で、21:42 の push はその24時間以内だった。
  **直し方**: 22:11（24時間経過後）に空コミットで再push → **約1分で反映**。
  切り分けは https://zenn.dev/dashboard/deploys のお知らせ欄が最短（拡張から読めた）。
- **症状**: 再push の `git commit` が `Unable to create '.git/index.lock': File exists` で失敗。
  **原因**: 別セッションの git が残した0バイトの lock（22:05）。**git プロセスは動いていなかった**。
  **直し方**: `ps aux | grep git` で実行中が無いことを確かめてから lock を消して再実行した。

### 次回への引き継ぎ事項・未解決の課題

- **次は12本目の題材選び**（`drafts/NETA.md` の在庫から、11本目のF章「スマホ・ブラウザ」以外を選ぶ）。
- **Zenn のレート制限を踏んだのはこれで2回目**（1回目は 8/22 の `openpyxl-row-height-autofit`）。
  同じ日に2本目を出すときは、**前回公開の時刻から24時間**を数えること。

---

## 2026-08-24（サブPC・夜）— 10本目の3点セットを、このPCから3媒体とも公開した

### 完了したこと

- **10本目「謄本は二枚で届く。一枚に潰したら、部屋の広さが車庫の広さになった」を3媒体とも公開**
  （素材は当日 `registry_parser.py` で直した実バグ。commit `8b0aad6`）
  - 本体 https://ai-tools-base.vercel.app/works/registry-annex-building
  - Zenn https://zenn.dev/shinsei99/articles/registry-pdf-merge-overwrite
  - note https://note.com/shinsei99/n/n62a9eda5388c （見出し画像＝みんなのフォトギャラリー
    「雨に濡れた駐車場」Photo by 稲垣純也。区画線＝面積の話に合わせた）
- `links` を追記して再デプロイ。**`npm run validate` の転載⚠️は 0 件**（残る4件は tools の review 空欄で別件）
- **note は当PCの Claude in Chrome 拡張から自動投稿**（8/22 の手順どおり。h2×6・p×31・a×3・1,579文字）

### 発生したエラーと解決策

- **症状**: `npx vercel --prod` が `{"status":"error","message":"Not authorized"}` で落ちる。
  **原因**: `whoami` は通る（個人 `daikyocorps-3085`）が、プロジェクトは **team: brain-dump** の持ち物。
  **直し方**: `--scope brain-dump` を明示。`publish.sh site` にも入れた（8/22 の節に既出だったが
  スクリプト側に入っておらず、同じ所で二度止まった）。
- **症状**: Claude in Chrome 拡張が `not connected` のまま繋がらない。
  **原因**: 起動していた Chrome が Visual Agent の自動操作用（`--headless
  --user-data-dir=~/.see/profile-chrome`）で、拡張の入っている Default プロファイルではなかった。
  **直し方**: `open -a "Google Chrome" https://claude.ai/chrome` で通常プロファイルを前に出したら繋がった。
- **note.com ドメインは拡張の権限外**（`editor.note.com` は可）。公開後のURL確認は `curl` で行った。

### 次回への引き継ぎ事項・未解決の課題

- **次は11本目の題材選び**（`drafts/PUBLISH.md` の順番表）。
- `drafts/README.md` の一覧は 10本目まで実態に合わせた。

---

# SESSION_LOG.md — AIツールベース 作業ログ

> **2026-08-17 に「AIツールラボ」から改名した。** これより下の過去ログには旧名
> `AIツールラボ` / `ai-tools-lab` / `ai-tools-lab-psi.vercel.app` がそのまま残っている。
> **当時の事実なので書き換えていない。** 読み替えること。

新しい項目は上に追記する（上が新しい）。

---

## 2026-08-23（サブPC）— 3媒体の本数を実データで数え直し、台帳の古い印を直した

### 完了したこと

- **「本体・Zenn・note の本数は合っているか」を実データで確認した。結果は 9 / 9 / 9 で揃っている。**
  数え方（推測ではなく実行して確認）:
  - Zenn … `./publish.sh status` → 9本すべて ✅（API `zenn.dev/api/articles?username=shinsei99`）
  - note … `curl -s 'https://note.com/api/v2/creators/shinsei99/contents?kind=note'` → `totalCount 9`
  - 本体 … `content/works/*.json` は15本だが、**転載対象は `category=realestate` の9本**
    （ツール5・メディア1は方針どおり本体のみ）。9本すべて `links` に Zenn と note が入っており、
    URLのslug/keyが上のAPI一覧と1件ずつ一致することも突き合わせた
- **台帳の古い印を直した**（実体は公開済みなのに書類だけ未公開のままだった）:
  - `drafts/PUBLISH.md` 7本目 … Zenn `ai-intake-hearing` は **8/20 23:40 に遅れて反映**、
    note `nanka-ugokanai` は **8/21 07:53 に公開**。両方 ⬜ のままだったので ✅ とURLに更新
  - `drafts/PUBLISH.md` 冒頭の本数（「Zenn 8本中7本」「note 3本公開」）を「9本すべて公開」に
  - `drafts/PUBLISH.md`「公開待ちの順番」表に 8/20・8/21・8/22 の実績行を足し、公開待ち0本を明記
  - `drafts/README.md` の9本目の行（⬜push済・上限で未反映 / ⬜Zenn待ち）を ✅公開 に
  - 直下 `TODO.md` の引き継ぎD章から「note はメインPCで出す」を削除（当日朝に自分で書いたが誤り）

### 発生したエラーと解決策

- **症状**: 8/21 の作業ログと `PUBLISH.md` で「note 1本が未公開」と読める状態が残っていた。
  **原因**: 8/21 に公開した際、`content/works/ai-ticket-counter.json` と作品ページは更新したが、
  **`drafts/PUBLISH.md` と `drafts/README.md` の表を更新していなかった**（公開手順の最後の
  「表に追記」が漏れた）。**直し方**: 公開の判定を書類ではなく **API の実データ**で取り直した。

### 次回への引き継ぎ事項・未解決の課題

- **次は10本目の題材選び**（`drafts/PUBLISH.md` の順番表）。公開待ちは0本。
- 公開したら**その場で `PUBLISH.md` と `drafts/README.md` の両方**を更新すること
  （今回ずれたのはこの2つ）。`npm run validate` は本体の `links` しか見ないので、
  表の書き漏らしは検出されない。

---

## 2026-08-22（サブPC・朝）— 9本目の外部公開を最後まで通した

### 完了したこと

- **Zenn `openpyxl-row-height-autofit` を公開**（08:2x）
  → https://zenn.dev/shinsei99/articles/openpyxl-row-height-autofit
  前夜に投稿上限で弾かれていた1本。**空コミットを push したら約30秒で反映**した
  （前回は9分待って404だったので、上限に掛かっているかどうかは待ち時間で見分けられる）。
- **note `moji-ga-kireteru` を公開**（08:29・サブPCから）
  → https://note.com/shinsei99/n/na1ff4ed050f4
  見出し画像はみんなのフォトギャラリーの「ルーラー」（Photo by r68929）。記事が
  「たぶんこれくらい」をやめて実測した話なので、目盛りの画像を選んだ。
- `content/works/excel-row-height.json` の `links` に Zenn / note を追記。
  `npm run validate` の**転載⚠️は 0 件**になった（残る⚠️4件は tools の review 空欄で別件）。
- `drafts/PUBLISH.md` の9本目の表を実績に更新。

### 発生したエラーと解決策

- **症状**: note の本文欄で `computer` の `cmd+v` を送っても貼り付かない（0文字のまま）。
  **原因**: 拡張が送る合成キーイベントには**OSのクリップボードが載らない**。
  **直し方**: `javascript_tool` で `DataTransfer` に `text/html` を入れた `ClipboardEvent('paste')`
  を作り、`.ProseMirror` に `dispatchEvent` した。**見出し・箇条書き・リンクはそのまま入る**
  （h2×4・ul×3・a×3 を数えて確認）。`md2html.py` の HTML は
  `md2html.convert()` を import して取り出し、base64 で JS に渡した。
- **前回「このPCからnoteへ自動投稿はできない」と書いたのは、条件付きで誤りだった。**
  できなかったのは `~/.mcp.json` の **Playwright（`--isolated --headless`）**の話で、
  **Claude in Chrome 拡張（＝普段のChromeのセッション）なら投稿できる**。8/22 に実証。
  ログイン済みのプロファイルをそのまま使うので、ボット検知にも掛からなかった。

### 次回への引き継ぎ事項・未解決の課題

- ✅ 本体サイトも再デプロイ済み（`npx vercel --prod --scope brain-dump` → Ready/Production・17秒）。
  本番 `/works/excel-row-height` から Zenn / note の両リンクが引けることを確認した。
  **次は10本目の題材選び**（`drafts/PUBLISH.md` の順番表）。
- `drafts/README.md` の一覧表の ✅公開 印が古いままなのは前回から継続。

---

## 2026-08-21（サブPC・夜）— 9本目「Excelの行の高さを実機で採寸した」を3媒体ぶん作成

### 完了したこと

- **9本目の3点セットを書いた**（素材は `chatwork-ai-manager` の業務日報Excel）。
  - 本体 `content/works/excel-row-height.json`（不動産・公開）
  - Zenn `drafts/zenn/openpyxl-row-height-autofit.md` → `~/articles/` へ複製・push 済み
  - note `drafts/note/moji-ga-kireteru.md`（技術用語なしの版）
- **記事に載せた数値は執筆時に取り直した実測**。憶測で書いていない:
  - 日報Excelを生成 → 実機 Excel に AppleScript で `autofit` → `row height` を読む
    → `1=27.0 4=20.0 5=36.0 6=18.0`（**1行=18pt / 2行=36pt**。1・4行目は高さ固定行なので対象外）
  - `openpyxl` で書き出したファイルを読み戻すと `[(1,28.0),(4,22.0),(5,36.0),(6,18.0)]` で一致
  - 旧式（`len()//37` × `14pt+4`）との差: 全角40文字＝32pt（4pt不足で切れる）／
    半角混じり55文字（表示幅66）＝32pt（実際は1行18ptで足りる＝余白過多）
- **本体を本番へ出した** → https://ai-tools-base.vercel.app/works/excel-row-height （200）。
  ページの見た目も `./va.sh shot` で確認済み（`.see/0821-221345-excel-row-height.png`）
- 記事化のために読み直して見つけた食い違いを1つ直した:
  `chatwork-ai-manager/services/daily_report_export.py` のコメントが「余白を見て68単位」の
  ままで、実装（74単位）とずれていた → コメントを実装に合わせた（動作は変わらない）

### 発生したエラーと解決策

- **症状**: `./publish.sh site`（＝`npx vercel --prod`）が `Not authorized` で失敗。
  **原因**: `npx vercel whoami` は通る（`daikyocorps-3085`）が、リンク先プロジェクトは
  team `brain-dump` にあり、既定スコープでは権限が無い。
  **直し方**: **`npx vercel --prod --scope brain-dump`** で成功（READY・target production）。
  → `publish.sh` の `npx vercel --prod` に `--scope brain-dump` を足すか、
  `npx vercel link --yes --project ai-tools-base --scope brain-dump` を1回やるのが恒久策（未実施）。
- **症状**: push しても Zenn に記事が出ない（**約9分待って404のまま**。`publish.sh status` も ⬜）。
  **原因**: 既知の「直近24時間の投稿数の上限で、その記事だけ黙ってデプロイされない」状態とみられる
  （直近の公開は `ai-intake-hearing` の **2026-08-20 23:40**）。**断定はしていない**
  ——上限のロジックは非開示で、デプロイのお知らせ欄はログインしないと読めないため。
  **直し方（未実施）**: 8/21 23:40 以降に**空コミットで再push**。
- `./va.sh shot` を `goto` 無しで叩くと、**前に開いていたページ（8505）を撮る**。
  必ず `./va.sh goto <url>` → `shot` の順で叩くこと。

### 次回への引き継ぎ事項・未解決の課題

- **★明日やること（この順）**:
  1. **8/21 23:40 以降**に `git commit --allow-empty -m "Zenn再push" && git push` →
     `./publish.sh status` が `openpyxl-row-height-autofit` ✅ になるまで確認
  2. Zennが✅になってから **note を手貼り**（`./publish.sh note moji-ga-kireteru` → 本文欄で ⌘V →
     見出し画像 → 公開）。**このPCからnoteへ自動投稿はできない**（ボット検知。8/21 の節を参照）
  3. 公開後、`content/works/excel-row-height.json` の `links` に Zenn / note のURLを追記し、
     `drafts/PUBLISH.md` の9本目の表を埋めて **`npx vercel --prod --scope brain-dump`**
- `npm run validate` の転載⚠️は現在 `excel-row-height` の1件（上の3が済めば消える）

---

## 2026-08-21（サブPC）— note の1本を出そうとして、このPCでは自動投稿できないと分かった

### 完了したこと

- **残っている転載漏れが `ai-ticket-counter` の1件だけだと確定させた。**
  `npm run validate` の転載漏れ警告はこれ1本（他は tools の review 空欄で別件）。
  本体 `/works/ai-ticket-counter` と Zenn `ai-intake-hearing` は**公開済み（ともに HTTP 200）**、
  **note だけ未公開**で `content/works/ai-ticket-counter.json` の `links` が空だった
- **原稿は完成していた**（`drafts/note/nanka-ugokanai.md`・100行）。末尾の導線に
  本体とZennのURLが入っており、**3つとも生存確認済み**＝死んだリンクは出ない
- `./publish.sh note nanka-ugokanai` でHTML 5,382バイトをクリップボードに載せるところまで完了

### 発生したエラーと解決策

- **症状**: note へ自動投稿しようとしたらログイン画面から先に進めなかった。
  **原因**: `~/.mcp.json` の Playwright MCP が **`--isolated --headless`** で動いており、
  **プロファイルが毎回まっさら＝ログイン状態が残らない**。headless なので人がログインもできない。
  **このPCの「入口A(MCP)」は Claude in Chrome拡張ではなく Playwright**
  （`./visual-agent-check.sh --mcp` の出力で確認）。
- **さらに**: `./va.sh start --headed` で画面つきブラウザを出してログインを試みたが、
  **note 側がボット検知でブロック**した。証拠はコンソール:
  `Failed to load resource: 429` ／ `pageerror solveSimpleChallenge is not defined` ／
  sandbox付きiframeの警告。ページ本文も空で返る。
  → **ボット検知の回避はしない方針なのでこの経路は断念した。**
  **自動操作ブラウザから note にログインしようとしないこと**（次の担当も同じ壁に当たる）。
- **切り分けた結果、拡張側は問題なかった**:

  | 確認項目 | 結果 | 確認方法 |
  |---|---|---|
  | 拡張のインストール | ✅ `fcoeoabgfenejglbffodgkkbkcdhcgfn`（Claude in Chrome） | Chrome の Extensions の manifest を読んだ |
  | 拡張の有効/無効 | ✅ 有効・v1.0.85・`disable_reasons` 空 | `Default/Secure Preferences` を読んだ |
  | claude.ai のログイン | ✅ ログイン済み（シン・Max） | 画面を撮って確認 |
  | Claude Code からの接続 | ❌ **ここだけ通らない** | `tabs_context_mcp` が「未接続」 |

  **未解決。** 残る容疑は ①拡張の**サイトごとの許可**が未設定（この拡張は実行前に
  サイト単位の許可が要る）②**Claude Code の自動更新が失敗している**
  （`✗ Auto-update failed · Run claude doctor` が出続けている。CLI 2.1.237 / 拡張 1.0.85 の
  噛み合わせは未確認）
- 途中で **Playwright用のChromeが残ってDockにChromeが2つ並んだ**。`--isolated` は
  一時プロファイル（`/var/folders/.../playwright_chromiumdev_profile-*`）を作るので
  `va.sh stop` では消えない。`pkill -f playwright_chromiumdev_profile` で片付けた

### 次回への引き継ぎ事項・未解決の課題

- **note の1本（`nanka-ugokanai`）は未公開のまま。** 出し方は2つ:
  1. **普段のChromeで手貼り**（確実・1分）: `./publish.sh note nanka-ugokanai` →
     note の本文欄で ⌘V → 見出し画像 → 公開
  2. **拡張を繋いで自動投稿**: 上の①②を潰す。**メインPCでは繋がっている**ので、
     急ぐならメインPCで出すのが早い
- **公開後にやること**（3点セットを完成させる）:
  1. `content/works/ai-ticket-counter.json` の `links` に **Zenn と note の両方のURL**を追記
     （Zennは `https://zenn.dev/shinsei99/articles/ai-intake-hearing`）
  2. `npm run validate` で転載漏れの ⚠️ が消えることを確認
  3. **`npx vercel --prod`**（Vercelはgit連携ではないので push だけでは本番が変わらない）
- **`drafts/README.md` の一覧表の ✅公開 印が古い。** photo-inpainter と agent-platform にしか
  付いていないが、実際は Zenn 8本すべて公開済み。次に触るとき現状に合わせる

---

## 2026-08-19（サブPC） — KeyLine の Zenn と note を「まとめて」公開

### 完了したこと

- **Zenn `ios-nfc-safari-entitlement` を公開**（22:09）
  → https://zenn.dev/shinsei99/articles/ios-nfc-safari-entitlement
  8/18 に投稿数の上限で弾かれていた1本。**24時間の窓が空いてから空コミットを push** して通した。
  これで Zenn は原稿8本中7本が公開済み（残りは `ai-intake-hearing`）。
- **note `who-has-the-key` を公開**（22:18・サブPCから）
  → https://note.com/shinsei99/n/nf24404f1b55b
  `md2html.py` の HTML をエディタに ⌘V で貼り、本文1,789字・見出し6・引用・リンクが一発で付いた。
- `content/works/keyline.json` の `links` に上の2本を追記。
  → `npm run validate` の keyline の ⚠️（転載がまだ）が消えたことを確認した。
- `drafts/PUBLISH.md` の8本目の表と「公開待ちの順番」を実績に合わせて更新。

### 発生したエラーと解決策

- **症状**: `./publish.sh zenn` を叩いても Zenn が再デプロイされない見込みだった。
  **原因**: `articles/` に変更が無いと `git commit` が失敗し、`git push` が
  "Everything up-to-date" で終わる＝**GitHub連携のフックが飛ばない**。
  **直し方**: `git commit --allow-empty` で空コミットを1つ作ってから push する。
  PUBLISH.md にも「変更が無ければ空コミットでよい」とあるが、`publish.sh zenn` 自体は
  空コミットを作らないので、**人が先に作る必要がある**。
- **症状**: note の見出し画像が、みんなのフォトギャラリーで「この画像を挿入」を押しても
  エディタに反映されない（2回試して2回とも）。本文には混入していない。
  **原因**: **未特定**。ブラウザ操作は3回目を試さず、本人に設定してもらって解決した。
  手で設定すれば普通に入る（南京錠・Photo by aoneko）。
- **判明した誤り**: PUBLISH.md と直下 TODO.md に「note は5〜6本とも未公開」と書いてあったが
  **誤りだった**。note の API（`https://note.com/api/v2/creators/shinsei99/contents?kind=note`）で
  実測したところ、**8/16 に2本すでに公開されていた**（`photo-inpainter` 20:20 /
  `ai-generated-building` 20:22）。PUBLISH.md の冒頭には「✅ 2本公開」と正しく書いてあり、
  下の表と食い違っていた。→ 表とサマリを実測値に直し、訂正の経緯も残した。
- **あわせて訂正**: 「note の投稿はメインPC担当（ブラウザ操作が要るため）」も実態と違う。
  **サブPCから投稿できる**（8/18・8/19 に実測）。

### 追記（同日・note を Zenn の本数に揃えた）

- **note を4本まとめて公開し、Zenn 7本 = note 7本に揃えた**（本人の指示）。
  `ai-always-on`(22:28) / `silent-failure`(22:30) / `scanned-pile`(22:33) / `upside-down`(22:36)。
  PUBLISH.md の「一度に出さない（TLが新着順なので互いに埋もれる）」に反する進め方だが、
  本数を揃える指示だったのでそのまま実施した。
- **見出し画像が入らなかった原因が分かった**: 「この画像を挿入」のあとに
  **トリミングの「保存」ダイアログ**が出る。ここを押していなかった。押せば普通に入る。
  → 手順: 画像アイコン → 記事にあう画像を選ぶ → 検索 → 画像 → **この画像を挿入 → 保存**。
- 画像は内容に合うものを選ぶこと。`scanned-pile` で最初に選んだ「書類の山」が
  実際は**札束**の画像だったので、目視して差し替えた（貼ったあと必ず見る）。
- `content/works/` の `links` を4件追記（chatwork-ai-manager / port-conflict /
  shorui-cabinet / baikai-generator）。`npm run validate` の転載⚠️は **ai-ticket-counter 1件だけ**になった。

### Zenn の投稿数の上限 — 「1日2本」は推測で、公式には非公開だった

`ai-intake-hearing` を `articles/` へ複製して push（22:35）したが、**弾かれた**。
デプロイ履歴の文言: 「次の記事は投稿数の上限に達したためデプロイされませんでした: ai-intake-hearing」。

このとき**直近24時間の公開は1本だけ**（22:09 の `ios-nfc-safari-entitlement`）だった。
つまり **「24時間に2本までなら通る」という理解は誤り**。公式FAQ（https://zenn.dev/faq/rate-limit）:

- 上限は「さまざまな要素を組み合わせたロジックにより決定」され、**不正防止のため開示していない**
- 記事は「**直近24時間以内の投稿数**（投稿予約中を含む）」で判定される
- 一定時間が経過すれば再び投稿できる

→ **本数で予定を組まない。** 毎回 `./publish.sh status` の ⬜ と
デプロイ履歴（https://zenn.dev/dashboard/deploys ・要ログイン）で確かめる。

### `./publish.sh site` が「Not authorized」で失敗した — サブPCからも本番デプロイはできる

**サブPCから Vercel 本番デプロイができることを実測した**（これまで「メインPC担当」としていた）。
ただし1回目は失敗した。症状 → 原因 → 直し方:

- **症状**: `npx vercel --prod` が `{"status":"error","reason":"deploy_failed","message":"Not authorized"}`。
  認証自体は通っている（`npx vercel whoami` → `daikyocorps-3085`、team は `brain-dump`）
- **原因**: `.vercel/project.json` の `projectName` が**旧名 `ai-tools-lab` のまま**だった。
  2026-08-17 の改名（ai-tools-lab → ai-tools-base）にリンク情報が追従していなかった
  （`.vercel/` は gitignore なので、git では直らない）
- **直し方**: `npx vercel link --yes --project ai-tools-base --scope brain-dump`。
  projectId と orgId は変わらず `projectName` だけが直り、そのあと通った

**`./publish.sh site` の「反映確認」は当てにならない。** デプロイが `Not authorized` で
落ちたあとも `https://ai-tools-base.vercel.app → HTTP 200` と表示した（既存のデプロイに
当たっているだけ）。**成否は「Aliased …」の行と、実際のページの中身で確かめること。**
今回は `curl .../works/keyline` と `/works/shorui-cabinet` に note のURLが出ることを見て確認した。

### 次回への引き継ぎ事項・未解決の課題

- **Zenn の残り1本 `ai-intake-hearing` は push 済みだが未反映**（上限で弾かれた）。
  時間を空けて **空コミットで再push** する。`articles/ai-intake-hearing.md` はもう置いてある。
- **note の残り1本 `nanka-ugokanai` は Zenn 待ち。** 本文から上の Zenn 記事にリンクしているので、
  Zenn が ✅ になってから出す（順序を崩さない）。
- **本番サイトへの反映が未了**: `content/works/keyline.json` を直したので
  `./publish.sh site`（Vercel 本番デプロイ）が要る。**外部に出る操作なので人の判断待ち。**
- 未修正のUI崩れ: 390px幅で比較表が横に484pxはみ出す（`div.table-scroll`）。ロゴも2行に折れる。

---

## 2026-08-17 — 「AIツールラボ」→「AIツールベース」に改名（メインPCで追従）

### 完了したこと
- 公開中のサイトは **https://ai-tools-base.vercel.app/**、名称は **AIツールベース** であることを実物で確認
  （h1「AIツールベース」／標語は「Claude Code を主軸に」のまま／制作記録10本）
- **リポジトリ側が旧名・旧URLのままだった**ので統一した（37ファイル）。
  `src/lib/site.ts` の `name`/`url`、layout・Hero の表示、`drafts/` の原稿と貼り付け用txt、
  リポジトリ直下 `articles/` のZenn記事5本、README/CLAUDE/HANDOFF/TODO
- `npm run validate` と `npm run build` が通ることを確認

### 発生したエラーと解決策
- **症状**: 公開済みのZenn記事5本・note2本のリンク先が404。
  **原因**: 旧URL `ai-tools-lab-psi.vercel.app` を意図的に削除したため（ややこしいので、という判断）。
  記事側のリンクは旧URLのまま残っていた。
  **直し方**: パス構成は新旧で同じなのでドメインだけ差し替え。`articles/` を push すれば
  Zennの5本は自動で直る。**noteは手作業**（Markdownが効かないため貼り直しが要る）。

### 次回への引き継ぎ事項・未解決の課題
- **note の公開済み2本（photo-inpainter / agent-platform）のリンクは手で直す**。
  `drafts/note/paste/*.txt` は更新済みなので、該当箇所だけ貼り替えればよい
- ~~フォルダ名は `ai-tools-lab` のまま~~ → **2026-08-17 夜に `ai-tools-base` へ統一**
  （サブPCが同じ日にフォルダごと改名しており、gitのマージでサブPC側を採用した）

> ↑この節はメインPCでの並行作業（同日）。サブPC側の節（下の「続き」）と内容が重なる。

---

## 2026-08-17（続き2）— note 公開済み2本の404リンクを修正

### 完了したこと
- **note 2本の本文リンクを新URLへ**（Chrome で代行・どちらも「更新する」まで完了）
  - `nad3f0dce2889`（半年あきらめていた開発が、2日で終わった話）
    … `AIツールラボ` → `AIツールベース` ＋ URL
  - `n0388b9c81b5f`（AIが、実際には存在しない建物を描いてきた話）
    … 同上 ＋ 制作記録リンク `/works/agent-platform`
- **3か所目が見つかった: note プロフィールの自己紹介欄**。旧URLが入っており
  **全記事の下部と クリエイターページに出ていた**。ご本人の判断で新サイト名ごと書き換え:
  「…制作記録「AIツールベース」: https://ai-tools-base.vercel.app」（107字／上限140字）
- リンク先の到達確認: 本体 200 ／ `/works/agent-platform` 200 ／ 旧URL 404（想定どおり）

### 分かったこと（再調査不要・note のエディタ）
- **リンクの文字を打ち替えると、追加した文字はリンクの外に出る。**
  「ラボ」→「ベース」と打つと下線が `AIツール` までしか掛からない。
  → **文字を直してから、リンク文字全体を選び直してリンクを貼り直す**のが正しい順序
- 選択は `shift+End` を使わないこと。**行末ではなく後続の段落まで飲み込む**
  （45文字選択された）。**`shift+Right` を文字数ぶん繰り返す**のが確実
- リンクを選ぶと出る 🔗 ボタンで **URL 欄に既存値が入った状態のポップアップ**が出る。
  `cmd+a` → 新URL → 「適用」
- 選択位置が画面の上端／下端に近いと**ツールバーが別の行に重なって誤クリックする**。
  対象の行を画面の中ほどに置いてから選択する
- 「更新する」の後に**シェア用ダイアログが自動で出る**。× で閉じるだけでよい（共有はしない）

### 次回への引き継ぎ事項・未解決の課題
- **残るは `git push` のみ（19:56 以降）**。これで Zenn 2本のリンクも直る

---

## 2026-08-17（続き）— Google Search Console を新URLへ移行

### 完了したこと
- **新プロパティ `https://ai-tools-base.vercel.app` を登録**（URL プレフィックス型）。
  **所有権は「自動確認」で通った**（確認方法: HTML タグ）。
  `src/app/layout.tsx` の `verification.google` が既に新URLで配信されていたため、
  トークンの貼り直しは不要だった
- **sitemap.xml を送信 → ステータス「成功しました」/ 検出ページ数 28**
  （8/16 の旧プロパティは26。ページが2つ増えている）
- **旧プロパティ `ai-tools-lab-psi.vercel.app` は残す**（ご本人の判断）。
  URL自体が404なので害はなく、旧URLのインデックスが消えていく過程を見られるため

### 分かったこと（再調査不要）
- **Search Console の「プロパティを追加」UI が変わっている。** プロパティ選択の
  プルダウン →「プロパティを追加」→ **「ウェブサイトを追加」**（Instagram/TikTok/X/YouTube と
  並ぶ新メニュー）→ そこで初めて「ドメイン / URL プレフィックス」の選択が出る
- **同じGoogleアカウントで別プロパティを確認済みだと、同じHTMLタグの値が使い回される。**
  新URLで同じ `verification.google` を配信していれば、追加した瞬間に自動確認される
  （＝タグの貼り直し・再デプロイは不要だった）
- 追加直後は画面が旧プロパティのままになる。
  `…/sitemaps?resource_id=<URLエンコードした新URL>` へ直接移動すると切り替わる

### 次回への引き継ぎ事項・未解決の課題
- **push はまだ（8/17 07:53 時点）。19:56 以降に行う**。下の節と同じ理由
- note 公開済み2本の404リンク修正は**未着手**（ブラウザ・本人）

---

## 2026-08-17 — 改名（AIツールラボ → AIツールベース）とURL移行

**サブPC（`/Users/apple`）で実施。** メインPCへの引き継ぎは**まだ行われていない**ため、
`HANDOFF.md` の「以後はメインPCで触る」は**この時点では未発効**。

### 完了したこと
- **改名の理由**: 旧名「AIツールラボ」は同種メディアに類似名が多く（JAPAN AI ラボ 等）、
  名前で埋もれると判断。**外部に出ていたのが4本（Zenn2・note2）だけの今が最小コスト**
- 表示名 `AIツールラボ` → `AIツールベース`（`src/lib/site.ts` / `layout.tsx` / `Hero.tsx`）
- slug・フォルダ名 `ai-tools-lab` → `ai-tools-base`（`git mv`。package.json / package-lock /
  `.gitignore` / ルート `CLAUDE.md` `TODO.md` / `content/works/*.json` / 全原稿）
- **本番URL `ai-tools-lab-psi.vercel.app` → `https://ai-tools-base.vercel.app`**
- `npm run validate` 通過（既存の⚠️4件＝review未記入、5件＝転載待ちのみ）／`npm run build` 成功

### 発生したエラーと解決策
- **`grep -rl` の結果を `for f in $FILES` で回したら、パスが改行ごと1つの文字列として
  perl に渡り、ほとんどのファイルが置換されなかった**（`Can't open TODO.md\n.gitignore\n…`）。
  それでも一部は成功していたため**「完了した」と誤認しかけた**。
  → **`find -print0 | xargs -0`** に変更。置換後は必ず `grep` で残存0件を確認する
- **`vercel project rename` をしても、綺麗なドメイン `ai-tools-base.vercel.app` は
  自動では付かない**。旧 `ai-tools-lab-psi.vercel.app` が本番ドメインのまま残る
- **`vercel alias set` でデプロイURLに直接エイリアスを張ると、Vercel の SSO 保護に掛かって
  302（`vercel.com/sso-api?url=…`）になる。** デプロイ単位のエイリアス扱いになるため。
  → **`vercel domains add <domain> <project>` でプロジェクトのドメインとして登録**すると 200 になる
- **`ai-tools-lab.vercel.app`（`-psi` 無し）は他人の別サイト**（title: `AI Tools Lab - AIツール比較・レビュー`）。
  自分のものと勘違いしかけた。**改名の判断を裏づける材料でもある**

### 分かったこと（再調査不要）
- **プロジェクト名を rename しても、旧ドメインは自動では失効しない。**
  rename 後も `ai-tools-lab-psi.vercel.app` は 200 を返し、canonical だけが新URLを指す状態になる。
  残す/消すは **`vercel alias rm` で選べる**

### 旧URLは削除した（ご本人の判断）
- 判断理由: **まだアクセスが無く、2つのURLが並存するほうがややこしい**。
  公開済み記事のリンクは**新URLで貼り直す**方針
- 削除したエイリアスは2つ: `ai-tools-lab-psi.vercel.app` / `ai-tools-lab-brain-dump.vercel.app`
  （`npx vercel alias rm <domain> --yes`）→ **どちらも 404 を確認**
- 現在のエイリアスは `ai-tools-base.vercel.app` / `ai-tools-base-brain-dump.vercel.app` の2つ

### 次回への引き継ぎ事項・未解決の課題
- **未コミット。** 改名の差分はまだ手元にある（`git mv` 済み・commit していない）
- **push は 8/17 19:56 以降にする。** リポジトリ直下 `articles/` には Zenn 未公開3本が
  置かれたままで、いま push しても投稿上限で弾かれる（公開済み2本のURL差し替えも同じ push で入る）
- **🔴 公開済み4本のリンクが今 404。旧URLを消したため。** 貼り直しが要る
  - **Zenn 2本** … 直下 `articles/` の原稿は新URLに直してある。**push すれば直る**
    （ただし 19:56 まで待つ。未公開3本が投稿上限で弾かれるため）
  - **note 2本** … **ブラウザで本人が修正**（本文の `AIツールラボ` と旧URL）
    - https://note.com/shinsei99/n/nad3f0dce2889
    - https://note.com/shinsei99/n/n0388b9c81b5f
- **Google Search Console は旧URLで登録されている。** 新URL `ai-tools-base.vercel.app` を
  別プロパティとして追加し、sitemap を出し直す（**ブラウザ・本人**）。旧プロパティは残してよい
- Vercel に **`drafts` という身に覚えのないプロジェクトがある**（9時間前に更新）。
  `drafts/` ディレクトリを誤ってデプロイした疑い。中身を確認して不要なら削除する

## 2026-08-16（続き4）— 集客の実装・制作記録2本追加・メインPCへ引き継ぎ

### 完了したこと
- **Google Search Console**: プロパティ登録 → 所有権確認（HTMLタグ方式）→ sitemap送信。
  ステータス「成功しました」/ 検出ページ数26。トークンは `src/app/layout.tsx` の
  `verification.google`（**消すと所有権が外れる**）
- **構造化データ（JSON-LD）**: Article / BreadcrumbList / WebSite
- **RSS `/feed.xml`** と `<link rel=alternate>` による自動検出
- **内部リンクの修復**（ここが最大の穴だった）
  - 制作記録の詳細ページ同士が繋がっていなかった → 末尾に「ほかの制作記録」3件
  - 記事内のツール名が**公式サイトへ直リンク**していて回遊が切れていた → `/tools/<slug>` へ
- **Zenn / note のプロフィールを整備**（自己紹介＋サイトURL。noteはクリエイターページにリンク表示）
- **制作記録を2本追加**（不動産）: `baikai-generator` / `ai-ticket-counter`。
  それぞれ Zenn・note の原稿も作成（計4本）→ 本体は本番反映済み
- **`HANDOFF.md` を作成**。以後の開発・公開は**メインPC**で行う

### 発生したエラーと解決策
- **`npx vercel --prod` の出力を `>/dev/null` に捨てて実行し、デプロイが走っていないのに
  成功したと誤認した**（本番に新ページが出ず404のままだった）。
  → **出力を見て `Aliased https://ai-tools-base.vercel.app` を目視確認する**
- **theta-viewer の制作記録は書けなかった。** サブPCの `README.md` は Vite の雛形のままで、
  `SESSION_LOG.md` も存在しない（gitにあるSESSION_LOGは5アプリぶんのみ）。
  **メインPCに未コミットの記録がある可能性が高い**ので保留。憶測では書かない
- note のプロフィールには**ウェブサイト専用の欄が無い**（ソーシャルリンクはX/Instagram等のみ）。
  自己紹介文にURLを書くとリンクになる

### 次回への引き継ぎ事項・未解決の課題
- **`ai-tools-lab/HANDOFF.md` を参照。** 引き継ぎ手順はそこに集約した
- 公開待ち: Zenn 5本 / note 5本（`drafts/PUBLISH.md` に日別の順番表あり）
- theta-viewer の記録はメインPCで素材を確認してから

## 2026-08-16（続き3）— 在庫を揃える方針・集客基盤・Zennのレート制限

### 完了したこと
- **転載の方針を確定**: 本体の**不動産カテゴリの公開記録**と Zenn / note の本数を揃える。
  ツール・ゲーム分類は本体のみ。**制作記録を1本増やしたら Zenn・note も同時に出す**
  （`ai-tools-lab/CLAUDE.md` に常駐。`npm run validate` が転載漏れを ⚠️ で出す）
- **psa-collection を本体からも外した**（`visibility: internal`。削除ではない）。
  他社サイトの内部APIを叩く手順の公開になるため
- **不動産の残り3本ぶんの原稿を Zenn・note とも作成**（計6本）
  - Zenn: `ai-agent-always-on` / `launchd-restart-loop` / `llm-pdf-split-gaps`
  - note: `ai-always-on` / `silent-failure` / `scanned-pile`
- **集客の基盤を入れて本番反映**（ここが全く無かった）
  - 全ページに OGP / Twitterカード、`metadataBase`、canonical
  - `works/[slug]/opengraph-image.tsx` で**記事ごとのOG画像を自動生成**（日本語表示も確認済み）
  - `sitemap.xml` / `robots.txt`（どちらも404だった）
  - URLは `src/lib/site.ts` の1箇所に集約（独自ドメイン移行はここだけ直す）

### 発生したエラーと解決策
- **Zennに3本pushしても反映されない** → 原因は **Zennの投稿レート制限**（記事は
  直近24時間の投稿数で判定。上限ロジックは非開示）。今日すでに2本出していたため弾かれた。
  **デプロイ履歴は「デプロイ成功」と表示され、お知らせ欄にだけ
  「投稿数の上限に達したためデプロイされませんでした」と出る**ので気づきにくい。
  → **原因の切り分けは https://zenn.dev/dashboard/deploys のお知らせ欄が最短**（要ログイン）
- **最初は絵文字（異体字セレクタ付き `🛎️` `✂️`）を疑ったが外れ。** 1コードポイントに
  直して再pushしても反映されなかった。修正自体は無害なので残してある
- Zennは**時間が経っても自動で再試行しない**。上限解除後にもう一度 push が要る
- 「booksディレクトリが見つかりません」の警告も出るが、本を出さないなら無視でよい

### 次回への引き継ぎ事項・未解決の課題
- **⚠️ 明日やること（順番厳守）**
  1. 空コミット push → Zenn 3本（`ai-agent-always-on` / `launchd-restart-loop` /
     `llm-pdf-split-gaps`）が公開されるのを API で確認
     （`curl -s "https://zenn.dev/api/articles?username=shinsei99&order=latest"`）
  2. note 3本を投稿（`python3 drafts/note/md2html.py <名前>` → 本文欄で ⌘V →
     見出し画像は「記事にあう画像を選ぶ」）。**note原稿にはZennのURLが埋めてある**ので
     Zennを先に出すこと
  3. `content/works/*.json` の `links` に両方のURLを追記 → `npx vercel --prod`
  4. `npm run validate` の転載漏れ警告が消えることを確認
- **Google Search Console に未登録**（sitemapができたので登録すると初期のインデックスが早い）。
  登録はブラウザ操作＝本人の作業
- 有料化（noteの有料記事）は**当面やらない**と判断。まず無料で流入を作る。
  やるならプロンプト単体ではなく「運用の型一式」か「1本ぶんの全ログ」で、
  本命は内蔵ツールのSaaS化（Stage 3）

## 2026-08-16（続き2）— Zenn公開2本・本体からの相互リンク

### 完了したこと
- **Zenn の GitHub連携が開通**（`shinsei99/project`）。ご本人がブラウザで App を承認 →
  こちらから空コミットを push（`34971fb`）→ **記事2本が公開**
  - https://zenn.dev/shinsei99/articles/photo-inpainter
  - https://zenn.dev/shinsei99/articles/gemini-api-traps
- **相互リンクの器を実装**: `workSchema` に `links`（`label` / `url` / `note`）を追加し、
  `/works/[slug]` に「この記録から書いた記事」ブロックを表示。
  `photo-inpainter` / `agent-platform` の2件にZennのURLを記入
- `drafts/PUBLISH.md` を更新（Zenn欄にURL記入、投稿手順を**GitHub連携前提**に書き換え）
- **note の原稿2本を投稿できる状態まで仕上げた**（投稿自体はブラウザ操作なので未実施）
  - 懸案だった「品質が低い原因を突き止めてほしい」の鍵カッコを**外して地の文にした**。
    実際の文面が不明なまま引用の体裁で載せられないため。趣旨（改善ではなく原因究明を頼んだ）は保持
  - 末尾の Zenn リンクを実URLへ差し替え。`ai-generated-building.md` には
    制作記録（`/works/agent-platform`）への導線を追加
  - `drafts/note/make_paste.py` を追加 → `drafts/note/paste/*.txt` を生成
- **note に2本公開**（Chrome拡張で投稿まで実施）
  - https://note.com/shinsei99/n/nad3f0dce2889 （半年あきらめていた開発が、2日で終わった話）
  - https://note.com/shinsei99/n/n0388b9c81b5f （AIが、実際には存在しない建物を描いてきた話）
  - 見出し画像は note の**みんなのフォトギャラリー**から設定（クレジットは note が自動表示）
  - `content/works/*.json` の `links` に note のURLを追記

### 発生したエラーと解決策
- **ブラウザ拡張はこのセッションでも未接続**（`Browser extension is not connected`）。
  前回「セッション再起動で使える」と書いたが**再起動しても繋がらなかった**。
  → **GitHub App の承認はご本人にブラウザで実施してもらった**。以後もこの承認系は代行できない
- **Zenn の公開状況はブラウザ無しで確認できる**: `zenn.dev/api/articles?username=<id>&order=latest`
  （公開JSON。0件なら連携が効いていない）。プロフィールHTMLの `__NEXT_DATA__` には
  記事一覧が入っていないので、そちらを見ても分からない
- `gh api /user/installations` は **403**（GitHub App 経由のトークンでないと一覧できない）。
  連携の有無を CLI から確認する用途には使えない
- **note の投稿は「HTMLをクリップボードに載せて貼る」のが最短**（`drafts/note/md2html.py`）。
  noteのエディタは**クリップボードの text/html を読む**ので、h2 / blockquote / ul / a が
  そのまま見出し・引用・箇条書き・リンクになる。**プレーンテキストで貼ると1行ずつ
  画面で見出し指定する羽目になり、実際に途中で断念した**。
  macOSは `pbcopy` がプレーンテキストしか置けないため、AppleScript の
  `set the clipboard to «data HTML…»`（16進）を使う。pyobjc は未導入で使えない
- **noteのMarkdownショートカット（行頭に `# `）は既存の行では効かない**。
  文字としてそのまま入るだけなので、記法での後付けは不可
- **見出し画像は「記事にあう画像を選ぶ」（みんなのフォトギャラリー）が速い**。
  `画像をアップロード` は**hidden な file input がアクセシビリティツリーに出ず**、
  file_upload でも掴めなかった（クリックするとネイティブのファイル選択が開いて操作不能）
- 素材選びの注意: ギャラリーには**実在の特定物件を写した写真**があり、タイトルに物件名が入る。
  「実在しない建物」の記事に使うと誤解を生むので外した（採用したのは
  タイトルに「AI生成画像」と明記されたイラスト）
- **note は Markdown が効かない**ので、Zennと同じ原稿をそのまま貼ると `##` や `**` が
  文字として出る。さらに**貼り付けた改行がそのまま行送りになる**ため、原稿の折り返しのまま
  貼るとスマホで不自然に改行される。→ 記法を落とし段落を1行に繋ぐ `make_paste.py` を用意した
  （見出し・引用は画面側で指定する前提で、対象行の一覧をファイル先頭に付ける）

### 次回への引き継ぎ事項・未解決の課題
- **Vercelはgit連携ではなく `vercel` CLI での手動デプロイ**（`.vercel/project.json` あり・
  CLIは `daikyocorps-3085` でログイン済み）。**pushしても本番は更新されない**。
  相互リンクを本番に出すには `npx vercel --prod` が要る（2026-08-16時点で**未実行**）
- note のアカウント作成・ログイン・メール認証は**ご本人の操作が必要**だった
  （Chrome拡張は接続できたが、認証情報の入力は代行しない領域）
- `drafts/note/photo-inpainter.md` の鍵カッコは外したが、**実際に打った文面を思い出したら
  そちらへ差し替えてよい**（趣旨は変えないこと）
- ツール4件（v0 / bolt / devin / windsurf）の `review` 未記入は**据え置き**（触ってから書く）

## 2026-08-16（続き）— Vercel公開・Zenn/note展開の準備

### 完了したこと
- **Stage 2 完了**: `/tools` `/tools/[slug]` `/works` `/works/[slug]` `/articles`
  `/articles/[slug]` `/history` を作成。**404が全て解消**
- **Vercel公開**: https://ai-tools-base.vercel.app （全ページ200確認）
- ヒーローを2カラム化し、右にターミナル画面のビジュアルを配置。
  h1はサイト名（AIツールラボ）、標語はサブタイトルへ降格（階層が逆転していた）
- **プロンプトの掲載方針を確定**: 体裁と語調は整えてよいが、
  **内容と粒度は変えない**（一言の指示を長い依頼に書き直さない）。型のコメントに明記
- Zenn/note用の原稿4本を `drafts/` に作成（photo-inpainter / agent-platform 素材）
- リポジトリ直下に `articles/` を作成（ZennのGitHub連携の参照先）

### 発生したエラーと解決策
- **Zennに記事が出ない（公開0件・404）** → 原因は **Zenn の GitHub App が
  未インストール**（github.com/settings/installations に無い）。
  連携が途中で終わっていた。**Appのインストールはブラウザでの承認が必須で、
  CLIからは実行できない**
- Zennは**pushを合図にデプロイする**ため、連携前のpushは取り込まれない。
  連携後に一度pushし直す必要がある（空コミットでよい）
- `articles/` に frontmatter の無い README を置いていたので退避した

### 次回への引き継ぎ事項・未解決の課題
- **⚠️ Claude in Chrome 拡張を入れたが、このセッションでは認識されない。**
  ブラウザツールは**セッション起動時に読み込まれる**ため、
  **拡張導入後に起動したセッションでないと使えない**。要セッション再起動
- 再起動後にやること:
  1. Zenn の GitHub App をインストール（`shinsei99/project` を許可）
  2. 空コミット＋pushでデプロイを起動 → 記事2本が公開される
  3. note のアカウント作成と投稿（原稿は `drafts/note/` に2本）
  4. 公開後、`drafts/PUBLISH.md` にURLを記入し、本体から相互リンクを張る
- ブラウザ操作を使わない場合は `drafts/zenn/paste/*.txt` を貼れば1本1分で出せる
- Zenn ID は **shinsei99**（アカウント作成済み・記事はまだ0件）

## 2026-08-16 — 新規プロジェクト立ち上げ（アーキテクチャ＋トップページ）

### 完了したこと
- `create-next-app` で雛形生成（Next.js 16.3.1 / React 19.2.8 / Tailwind v4 / TS / ESLint / src / App Router）
- **設計を4点で固定**: ①コンテンツはファイル ②読み出しは `source.ts` の1箇所 ③zodスキーマ1本
  ④制作記録は `visibility` 必須で `public` 以外を返さない
- 型定義 `src/lib/schema.ts`（Tool / Article / Work / Category）と読み出し層3本
- コンテンツ: ツール9件・記事4本・制作記録11本（公開9／社内2）
- トップページ: Hero／特徴4枚／**比較テーブル（検索・カテゴリ・無料枠・並べ替え）**／制作記録／記事カード
- フリー写真の取り込み（`npm run photos`）とクレジット表示の仕組み
- `npm run validate`（コンテンツ検証。slug不一致・visibility欠落・個人情報の混入を検査）
- 本番ビルド成功（約9秒）、開発サーバー `127.0.0.1:3004` で HTTP 200 を確認

### 発生したエラーと解決策
- **CC BY / BY-SA の写真は出典表示が義務** → 表示を消した瞬間に違反になる構造が危ういと判断し、
  Openverse の絞り込みを `license_type=commercial` から **`license=cc0,pdm`** へ変更。
  取り直して全5枚が CC0 / パブリックドメインになった（表示義務なし）
- 検証スクリプトの敬称チェックが「仕**様**」に誤反応 → 一般語（仕様・同様・様々…）を先に除去してから判定。
  誤検知を放置すると本物の警告まで無視されるようになるため潰した

### 次回への引き継ぎ事項・未解決の課題
- **Stage 2 が未着手**: `/tools`・`/tools/[slug]`・`/articles`・`/articles/[slug]`（MDX本文の描画）・
  `/history`・`/works`・`/works/[slug]`。現在リンク先が存在しないのはトップからの導線のみ
- MDXは **frontmatter しか読んでいない**（本文の描画は Stage 2）
- ツール4件（v0 / bolt / devin / windsurf）が `review`（評価の根拠）未記入。**根拠のない点数は載せない**方針なので、
  実際に触ってから書くか、点数を下げるか判断する
- 未決: 公開先（Vercel想定でよいか）／独自ドメイン／収益の形（アフィリエイト・有料ツール・両方）
