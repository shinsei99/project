# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ★★ 作業ルール（PDCA・引き継ぎ）— 起動直後に必ず実行

セッションが切れても後任が同じ状態から続けられるようにするための決まり。
**この節は全アプリ共通で、例外なく守る。**

### 0. 起動したら、挨拶より先に読む

1. `CLAUDE.md`（このファイル）
2. `TODO.md`（リポジトリ直下）… **どのアプリで何が進行中かの索引**。全体像はここだけで掴む
3. 作業対象のアプリが決まったら `<アプリ>/SESSION_LOG.md` と `<アプリ>/TODO.md`

読み終えてから挨拶し、**「前回はどこまで進んでいて、次は何をする状態か」を1〜2行で述べる**。
どのアプリの作業か分からないうちは直下の `TODO.md` までで止めてよい（全アプリのログを
先読みしない）。ファイルが無いアプリは、そのアプリで最初に作業するときに作る。

### 1. Plan（計画）／ Do（実行）

着手前に、これからやることを `<アプリ>/TODO.md` に書く（1行でよい）。
書いてからコードを書き、テストする。作業中に増えた課題もその場で追記する。

### 2. Check（評価）

テストが落ちた・エラーが出たときは、**原因と、なぜその直し方で直るのか**まで見る。
現象だけ消して先に進まない。調べて分かった事実（APIの仕様、はまりどころ）は
アプリの `README.md` に残す。同じ調査を次の担当が繰り返さないため。

### 3. Act（改善・記録）

作業の区切り（またはセッションの終わり）に、`<アプリ>/SESSION_LOG.md` の**先頭**へ
新しい日付の節を追記する。**上書きせず必ず追記**。書式は次の3見出しで統一する。

```markdown
## 2026-08-13

### 完了したこと
-

### 発生したエラーと解決策
- 症状 → 原因 → 直し方（原因が分かっていないなら「未特定」と書く）

### 次回への引き継ぎ事項・未解決の課題
-
```

同時に、直下の `TODO.md` のそのアプリの行を現状に合わせて1行で書き換える
（索引なので詳細は書かない。詳細はアプリ側のログにある）。

### 書くときの原則

- **憶測を事実として書かない。** 確かめていないことは「未確認」と明記する
- 失敗した案・やめた案も理由つきで残す（後任が同じ失敗を繰り返さないため）
- 数値は測った値を書く（「速くなった」ではなく「4.2秒 → 1.1秒」）

---

## ★ 最優先事項 — 全アプリ一覧（2026-08-07時点）

**カテゴリ:** 不動産 / ツール / ゲーム の3分類（全50本）※不動産30・ツール14・ゲーム6  
**社内LANルール:** 不動産カテゴリの完成済みのみ共有（launchd常時起動）

### 不動産（30本）

| アプリ名 | フォルダ名 | port | 社内LAN | 外部公開 |
|---|---|---|---|---|
| 手書き検針記録 | handwriting-ocr | — | 開発中 | — |
| 見積書自動生成ツール | quote-generator | 8503 | ✅ | — |
| 物件管理案内文ジェネレーター | property-notice-generator | 8504 | ✅ | — |
| マイソクコンバーター | maisoku-converter | 8505 | ✅ | — |
| 不動産写真AI | photo-inpainter | 8506 | ✅ | — |
| 原状回復費用自動精算 | restoration-calculator | 8508 | ✅ | — |
| AI不動産価格査定 | realestate-valuation | 8509 | ✅ | — |
| 決済案内書自動作成 | settlement-creator | 8510 | ✅ | — |
| 売買書類クロスチェック | legal-crosscheck | — | 開発中 | — |
| 間取り図トレーサー | madori-tracer | 8511 | ✅ | — |
| THETAパノラマ3D空間化 | theta-viewer | 8512 | ✅ | GitHub Pages |
| 特約条項ジェネレーター | tokuyaku-generator | 8513 | ✅ | — |
| 入金突合（消込）システム | payment-reconciler | 8514 | ✅ | — |
| 物件写真一括リサイズ | image-resizer | 8515 | ✅ | GitHub Pages |
| 顧客追客マネージャー | tsuikyaku-crm | 8516 | ✅ | — |
| AI重説調査〜Excel自動入力 | jyuusetsu-research | — | 開発中 | — |
| 媒介契約書ジェネレーター | baikai-generator | 8517 | ✅ | — |
| AI受付＆起票カウンター | ai-ticket-counter | 8600 | ✅ | — |
| マンション・ビル管理 | building-manager | — | 開発中 | — |
| オーナー送金・月次締めマネージャー | owner-payout-tracker | 8519 | ✅ | — |
| 横断ファイル検索ブラウザ | file-finder | 8520 | ✅ | — |
| 不動産・金融マスター電卓 | realestate-calc | 8507 | ✅ | GitHub Pages / App Store ✅ |
| 業務マニュアル（Web） | gyomu-manual | 8521 | ✅ | — |
| 駐車場配置図ビューア | parking-map | 8522 | ✅ | — |
| 覚書・合意書ジェネレーター | memorandum-generator | 8524 | ✅ | — |
| 送付書メーカー | soufu-maker | 8525 | ✅ | — |
| 書類キャビネット（紙書類の所在管理・ファイル単位） | shorui-cabinet | 8528 | ✅ | — |
| 書類キャビネット スマホ用（撮影→Dropbox取込） | shorui-mobile | — | ー（Vercel・pass保護） | Vercel（shorui-mobile.vercel.app） |
| マルチプロダクション（企画→紙面→パワポ→音声→動画→SNS） | agent-platform | 8532 | 開発中（完成まで127.0.0.1） | — |
| AI業務マネージャー（Chatwork/LINE常駐AIエージェント） | chatwork-ai-manager | 8540(画面)/8530(LINE) | ✅（画面0.0.0.0） | LINE(ngrok) |

### ツール（14本）※社内LAN共有なし

| アプリ名 | フォルダ名 | port | 外部公開 |
|---|---|---|---|
| 送付書ジェネレーター | soufu-generator | 8518 | — |
| デジタル書斎 | digital-shosai | 3001 | — |
| ブレイン・ダンプ自動整理 | brain-dump | 3002 | Vercel（brain-dump-sable-one.vercel.app） |
| スクラップメモ + PetaPeta Clipper | scrapmemo-petapeta + petapeta-extension | — | GitHub Pages / App Store ✅（1.0.2 build6 配信済み） |
| 水泳記録トラッカー | swim-tracker-react | — | GitHub Pages / App Store ✅ |
| ママカウンター | mom-counter | — | GitHub Pages / App Store ✅ v1.0.1 |
| Mac一斉メール送信 | mail-merge-pro | — | Macアプリ |
| フォトリメイク | photo-remake | — | iOS App Store配信済み ✅ |
| 買取DMジェネレーター | kaitori-dm-maker | 8526 | — |
| PSA保有カード管理 | psa-collection | 8527 | — |
| パシャカロ！（撮るだけカロリー記録） | pasha-calo | 3003 | Vercel（pasha-calo.vercel.app） |
| ポケモンカード図鑑（全31,520枚・画像100%収録） | pokecard-dex | 8531 | — |
| チラシクリエーター（物件チラシ・型10種／物件サイト生成） | flyer-creator | 8529 | 物件サイトのみ daikyocorp.co.jp/slowlife/ |
| AIツールベース（Claude Code主軸の比較メディア＋制作記録） | ai-tools-base | 3004 | — |

### ゲーム（6本）※社内LAN共有なし

| アプリ名 | フォルダ名 | 外部公開 |
|---|---|---|
| ひよこ防衛軍 | piyo-defense | GitHub Pages |
| カラー重力ゲーム | color-gravity | GitHub Pages |
| サイボーグ防衛軍 | cyborg-defense | GitHub Pages |
| にゃんこ大脱出 | neko-escape | GitHub Pages |
| にゃんこのアイス屋さん | nyanko-ice | iOS App Store申請中 |
| ネオンブロック | neon-blocks | iOS App Store配信済み ✅ |

### 業務マニュアル（Web）補足 ※不動産カテゴリに計上

- **大京商事 業務マニュアル（Web）** … 自己完結HTML一枚（22マニュアル）。所在: `gyomu-manual/業務マニュアル.html`（2026-07-10作成）。生成スクリプト: `gyomu-manual/generate.py`（`python3 generate.py` で再生成可）。port無し・ブラウザで直接開く運用。

### parking-map（駐車場配置図ビューア）補足

- 第一号: 角屋(横堤)モータープール（全41区画）。`serve.py` が起動の度にレントロールxlsxを読み最新の空き状況を反映（port 8522）。車室レイアウトは`template.html`に固定、中身のみ動的差し込み。個人情報を含む静的版はgitignore対象。他物件（大京モータープール／本庄西／ベリエール等）は今後同方式で展開予定。launchd登録済み・社内LAN共有済み（2026-07-14、com.shinsei.parking-map、`serve.py --daemon`でブラウザ自動起動を抑制）。

### 買取DMジェネレーター（kaitori-dm-maker）補足 ※ツール・port 8526

- 所有者台帳（確定15列・1物件1行：`NO/市/所在/地番/地目/地積・㎡/建物種類/建物構造/床面積・㎡/登記名義人/持分/郵便番号/現住所/電話番号/備考`）から、未活用地・空き家の**買取DM（Word）を差し込み量産**。文面は「建物買取DM横書き_改良版」準拠（ネイビー見出し・4メリット・約40万円囲みボックス・新誠/大京署名切替）。Streamlit+python-docx。
- **謄本PDF取込**：サイドバー「台帳更新」から謄本を複数（5件程度）アップ→AI読取→台帳に行追加。読取は**同リポジトリの`baikai-generator/services/registry_parser.py`を再利用**（`claude` CLIビジョン、パスは`shutil.which`で解決）。市/所在の分離・地目/地積・建物種類/構造/床面積・登記名義人/現住所を自動抽出。「1ファイル=1物件」/「全ファイル=1物件に統合」を選択可。
- **差出人**はサイドバーで追加・編集・削除（`senders.json`に保存。無ければコード内`DEFAULT_SENDERS`から生成）。DM一覧は各行チェックで送付先選択（既定全選択）、結合docx/個別ZIP出力。
- `senders.json`は個人情報を含むため**gitignore**（公開リポジトリに出さない）。メインPCへはコード内`DEFAULT_SENDERS`が既定として引き継がれる。launchd未登録（ツール分類のため社内LAN共有なし）。

### PSA保有カード管理（psa-collection）補足 ※ツール・port 8527

- PSA「My Collection」エクスポートCSV（`data/collection.csv`）を読み、**保有カードの検索・絞り込み・保管場所記録**を行う在庫管理Streamlit。初回取込は871件（保有381 / 売却済490、PSA10=541、ほぼポケカ日本語版＋ワンピースTCG）。
- 保管場所・メモは`data/storage_notes.json`に**証明書番号キー**で別管理。CSVを丸ごと差し替えても消えない設計（サイドバー「データ更新」でアップロード差し替え）。一覧の`PSA`列は`psacard.com/cert/<番号>`へのリンク。
- **カード画像**（🖼ギャラリータブ）: **871枚取得済み**（保有381＋売却済490・443MB）。`data/images/<cert>.jpg`に永久キャッシュ、一覧用サムネは`data/thumbs/`に初回自動生成。
- **画像の取得ルート（重要・再調査不要）**: PSA公開APIは**承認制で403**（`Access to this API is limited to approved customers`）。トークン自体は有効（無効トークンなら429、有効だと403に変わる）だがアカウント承認が必要で、申請窓口はページ上に無く`collectors-apis@collectors.com`のみ。→ **実際に使えたのは`app.collectors.com`のサイト内部API**。ログイン済みSafariで`do JavaScript`（設定: 詳細>Webデベロッパ用の機能を表示 → 開発>Apple EventsからのJavaScriptを許可）し、`collection.list`（`cursor`=ページ番号/`pageSize`/`totalItems`、画像URLはnull）→ `collection.images`（listのitemsを渡すと`collectibleId`キーで`original/large/medium/small/thumbnail`）の2段。入力は`{"0":"<JSONの16進エンコード>"}`形式。画像実体は`d1htnxwo4o0jhw.cloudfront.net`で**認証不要**。スクリプトは`harvest_collectors.js`＋`import_from_web.py`。**承認・回数制限とも不要**。
- **psacard.comの証明書ページはCloudflareで403**。サーバー側スクレイピングは不可。
- `data/`は保有明細と資産額を含むため**gitignore**（公開リポジトリに出さない）。他PCではCSVを`data/collection.csv`に置いて起動。launchd未登録（ツール分類のため社内LAN共有なし）。
- 元データの制約: `My Cost`/`My Value`/`Date Acquired`/`Source`/`My Notes`はPSA側で全件空欄 → **仕入値ベースの利益は算出不可**（売却額−手数料=手取り まで）。`Year`に`1998-99`形式が4件混在するため先頭4桁を数値年として扱う。
- **サイドバー「表示対象」は6区分**（保有中(Vault)=Vault Status Vaulted+Vault Bound / 保有中(Home)=Unvaulted / アルバム / 鑑定中 / 売却済 / すべて）。売却済ビューは売却額に加え**現在推定額（PSA Estimate列。全件入っている）**を併記（カード=緑字/一覧列/集計「現在推定額 合計・売却比」）。カードのキャプションはmarkdownとHTML混在だと生タグ化するため**純HTMLのdiv**で描画すること。
- **アルバム（コレクションアルバム）**: 保有中(Home/Vault)から選んだカードで名前つきアルバムを作る（`data/albums.json`＝アルバム名→cert配列、gitignore）。4列×10行/ページのバインダー、各カードにHOME/VAULTバッジ。並べ替えは**Streamlit標準ボタンの「つかむ→ここへ」方式**（session_stateで選択保持、ページ跨ぎ移動可）。画像は`_data_uri()`でbase64直埋め（`st.image`はメディアID失効エラーが出るため）。
  - **経緯（重要・再実装しないこと）**: 当初ドラッグ&ドロップで作ったが実環境で全滅。①`streamlit-sortables`は`<img>`を生テキスト表示でNG、②自作iframeコンポーネント（HTML5 DnD／ポインタ追従クローン）はSafariのネイティブ画像ドラッグ横取り＋**iframeの強キャッシュ**で不安定（URL変更しても解決せず）。→ **iframe/JSを一切使わないStreamlit標準ボタン方式が唯一確実**。ドラッグに戻さない。
- **鑑定中タブ（グレーディング申請中）**: `data/orders.json`（gitignore）を読み、進行中オーダーの**個別カードを画像・カード名・cert番号・現在工程つきで一覧**。取得は`./update_orders.sh`→`harvest_orders.js`をログイン済みSafariで実行。**psacard.comのtRPC API**を2段で叩く（画像取得のapp.collectors.comとは別サイト・入力は**base64**）: `orders.list`（申請一覧、status=Processing/Shipped/Completed）→ 進行中各件で`orders.get`（入力`{submissionNumber,orderNumber}`。返り`specReviewResults[]`=カード明細/`images{certID->[{imageSide:1表/2裏,thumbnail…}]}`/`orderProgressSteps[]`。現在工程=最初の未完了step）。画像は`d1htnxwo4o0jhw.cloudfront.net`（認証不要）。前提: Safari「開発>Apple EventsからのJavaScriptを許可」ON＋psacard.comログイン。
- **Vaultをオーダー（提出）別に絞り込み＋鑑定番号ソート（2026-08-07）**: Vaultビューのサイドバーに「オーダー（提出）」selectboxを追加。各カードがどの提出オーダー由来かは `orders.json` の **`certOrders`（cert番号→オーダー情報）** で判定。**重要・再調査不要**: `orders.get` は **進行中(Processing)は `specReviewResults[]`（`certNo`）だが、完了・発送済(Completed/Shipped)は空 → 代わりに `psaCerts[]`（`certNumber`）にカード明細が入る**（`trackingNumber:"Shipped to Vault"`でVault確認可）。`harvest_orders.js` は全オーダーで `orders.get` を叩き両方から `certOrders` を構築（鑑定中タブ用 `cards` は従来どおり進行中のみ）。全オーダー処理で20秒超えるため `update_orders.sh` のポーリングは60秒。並べ替えに「鑑定番号が小さい/大きい順」を追加（`cert_num`＝Cert Numberの数値列。桁数差があるため文字列ソート不可）。
- **CSVアップロードと同時に画像自動取得（2026-08-07）**: 「📥 データ更新」の「画像も自動取得」チェック（既定ON）で、差し替え後に不足cert分だけ `fetch_new_images.sh`（`harvest_collectors.js`→`import_from_web.py`）をSafari経由で実行。画像はCSVに含まれず `data/images/<cert>.jpg` の別キャッシュのため、CSV差し替え単体では新カードの画像は出ない。未ログイン時は更新のみ成功しフォールバック案内。

### マルチプロダクション（agent-platform）補足 ※不動産・port 8532・開発中

- 「企画からパワポ・ナレーション音声・解説動画(mp4)・SNS告知文まで全部作って」という**1文の指示**を、**11部隊**（司令塔／リサーチャー／企画構成／画像生成／パワポ／音声／動画／高速チェッカー／SNS／法務／QA）が順に処理して成果物一式を出す。画面はStreamlit（**入力フォーム／実行状況（部隊ごとの進捗ボード＋日本語ログ）／成果物**の3タブ）、CLIは `main_orchestrator.py`。
- **設計の芯＝縮退モード**: APIキーが1つも無くても全工程が完走する（雛形テキスト・Pillowの簡易画像・無音WAVで代替）。縮退した工程は画面とレポートで ⚠️ 表示。これが無いと1つのキー未設定でパイプライン全体が死んでデバッグ不能になる。
- **LLMは役割で抽象化**（`reasoning` / `longcontext` / `fast` / `light`）。`.env` の `AP_ROUTE_*` で `anthropic / claude_cli / openai / gemini / groq` を差し替え可能。**`claude` CLI がフォールバックに入っているのでANTHROPICキー無しでも司令塔・企画・法務が動く**。
- **★費用方針: このアプリは「全部無料の範囲」で動かす（`AP_ALLOW_PAID=0` が既定）。** 有料機能は一切呼ばない。**AI画像生成（Gemini画像/DALL-E/Stability）もVeo（画像→動画）も無料枠が無い**（2026-08-14 確認）。代わりに ①実写真のアップロード ②**HTML+CSS→Playwrightで作図**（1枚2秒・無料・**日本語が崩れない**）③**ケンバーンズ**（ffmpegのズーム/パン・無料・写真の中身は変わらない）で作る。**Veoは実測で元の写真に無い建物を作った**ため、実在物件の広告には使用不可（8秒$0.80）。
- **キー在庫の実測（2026-08-14）**: Gemini=**実キーあり**（`brain-dump/.env.local`・`pasha-calo/.env.local`・`madori-tracer/.secret_key` の3箇所。中身は同一・`AQ.`で始まる53文字。`.env`へコピー済み）、Anthropic=`madori-tracer/.env.local`のものは17文字のプレースホルダで**実キーではない**、OpenAI/Groq/ElevenLabs/Stability=**なし**。→ 文章系は全て実動、**画像もGeminiで実生成できる**、音声はgTTS。
- **Gemini運用の要点（再調査不要）**: ①SDKは**新しい`google-genai`**（旧`google-generativeai`は提供終了）。②**`gemini-2.0-flash`は404で提供終了** → 既定は`gemini-3.5-flash`。③**Gemini 3.xは「思考」にも出力トークンを使う**ので、JSONを求めるときは`response_mime_type="application/json"`＋出力枠3倍（最低8000）にしないと本文が空/途中で切れる（実測: 失敗→14.5秒で成功）。④**タイムアウトはミリ秒**指定（`types.HttpOptions(timeout=…)`）。未指定だと5分以上ハングする。⑤画像は`gemini-3.1-flash-image`で**1枚60秒・約600KB**。
- **動画の実測**: 2分13秒・1080pの書き出しにIntel Macで**約10分** → 既定を**720p＋`veryfast`＋マルチスレッド**に変更。書き出し途中のmp4は`moov atom not found`で再生できない（moviepyはヘッダを最後に書く）ため、**一時名で書いてrename**する実装にしてある。
- **音が出ないときはまずMac本体のミュートを疑う**（`osascript -e 'get volume settings'`）。実際に`output muted:true`で「音が無い」と誤認した。
- **ffmpeg未導入のMac**なので `imageio-ffmpeg` 同梱バイナリを `IMAGEIO_FFMPEG_EXE` に流して moviepy に使わせる。moviepy は v1/v2 で API名が違う（`set_audio`→`with_audio`）ため互換シムあり。
- `.env` と `output/`（生成物）は**gitignore**。
- **分類は不動産（2026-08-16変更）。ただし開発中なので `run.sh` はまだ `127.0.0.1` バインド・launchd未登録。**
  社内LAN共有は「不動産カテゴリの**完成済み**のみ」の決まりなので、完成時に `0.0.0.0` へ変えて
  launchd に登録する（そのとき下の「バインド先のルール」の表も直すこと）。

### AI業務マネージャー（chatwork-ai-manager）補足 ※不動産・画面8540／LINE8530

- 詳細は `chatwork-ai-manager/README.md`（gitに入っている）と、同フォルダの `CLAUDE.md` / `TODO.md` /
  `SESSION_LOG.md`（識別子を含むため**gitignore**。Dropbox-個人のtarで運ぶ）。
- **⚠️ worker / LINE webhook / ngrok は「同時に1台のPCだけ」。** 2台で動かすとChatwork・LINEへ
  二重返信し、ngrok固定ドメインを奪い合う。移すときは先に旧PCで
  `launchctl unload ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager*.plist`。
- **PCをまたぐ引き継ぎ**: コードはgit、機密（secrets・`data/app.db`・内部docs・ngrok token）は
  `handoff_export.sh` → Dropbox-個人 → `handoff_import.sh`。**DBは双方向マージできない**ので、
  常駐を移す直前に必ず export→import で最新へ揃える。
- Python は **`/usr/bin/python3` 固定**（venv Python だと `claude` サブプロセスが SIGSEGV）。

### チラシクリエーター（flyer-creator）補足 ※ツール・port 8529

- 旧称「加東 貸家チラシメーカー」・旧フォルダ名 `kato-flyer`（**2026-08-15 に改称**）。加東市秋津の貸家の客付け一式（A4チラシ＋物件サイト＋看板の元データ）。紙とWebが同じ `properties.py` を読むので、片方を直せば両方に反映される。
- **紙面の型10種・配色9種は `../agent-platform`（マルチプロダクション）のエンジンを借りている。コピーしていない。** 呼び方は **agent-platform の `.venv/bin/python` を別プロセスで動かす**方式（`engine.py`）。理由: エンジンは `import tools` で16アイテム（numpy・moviepy・playwright…）を読むため、こちらの `.venv` に同じものを入れると両方が壊れやすい。**flyer-creator 側に playwright は不要**。agent-platform が無いPCでは「これまでの型」（PIL版）だけで動く。
  - **★型・レイアウト・下帯・配色を直すときは `agent-platform/core/{layouts,blocks,previews}.py` を直す（flyer-creator 側に型の実体は無い）。1箇所直せばマルチプロダクションとチラシクリエーターの両方に反映される＝共通。** flyer-creator の `engine.py` はその型を呼ぶ橋渡し（`build_content` で `flyer.Flyer`→content へ翻訳・renderは `layouts.build()` 経由）だけ。型を直したら `agent-platform/.cache/previews/*.png` を消して見本を作り直す。逆に「チラシだけ変えたい」変更も、共通なのでマルチにも出る点に注意。
- **配色の既定 橙 `#f07c1e` × 濃紺 `#1b2340` は変えないこと。** 現地写真に重ねて検証した色（木立にも壁にも負けず工事看板にも見えない）。エンジンの `sunset`（`#e2701a`）で代用しない。
- **写真の安全装置3段構え（絶対に外さない）**: ①写真ソースは Dropbox 撮影フォルダのみ ②`DENY`（身分証・免許・申込・契約…）を候補から除外 ③人が選んだ写真がない物件は書き出さない。案件フォルダに**入居申込者の身分証と申込書が同居**しており、以前サイトの生成物に入りかけた（公開前に破棄・流出なし）。
- 集計の閲覧キーは `.stats_key`（gitignore）。`stats.php?k=…` で見る。**ソースにも文書にも書かない**。
- gitに入れるのは**コードと文書だけ**。`.venv` / `data/`（賃貸資料74MB・型サンプル）/ `site/`（生成物）は除外。旧免許番号(1)第58258号が焼き込まれた `assets/spm_logo_white.png` も配らない（使うのは `spm_logo_white_name.png`）。
- 物件サイトは **https://daikyocorp.co.jp/slowlife/** に公開済み（募集中4件＋賃貸中11件）。FTP接続情報は `theta-viewer/server/ftp-config.json`（gitignore）。

### 書類キャビネット（shorui-cabinet）補足 ※不動産・port 8528・社内LAN共有化（2026-08-12）

- **社内共有化**: `run.sh` を `0.0.0.0` バインドに変更しlaunchd常時起動（`192.168.1.105:8528`）。配布は他アプリと同じ作法で **Dropbox共有フォルダ**（`…/（★必読★）新共有フォルダ/社内ツール/`）に `書類キャビネット.url`（URL=http://192.168.1.105:8528）＋`icons/書類キャビネット.ico`、**Mac用**に `Desktop/社内ツール/書類キャビネット.app`（launcherは`open http://localhost:8528`・`AppIcon.icns`）。アイコン生成元は `shorui-cabinet/icon-src/`（PILで白いキャビネット×インディゴ、`.ico`/`.icns`両方）。
- **⚠️ launchd常時起動だとDropbox取込フォルダ（`~/Library/CloudStorage/…/書類取込`）を読めない**（macOS TCC。CloudStorageは保護領域）。**Python本体にフルディスクアクセスを付与しても効かない**（TCCの“責任プロセス”がlaunchdの`ProgramArguments[0]`=`/bin/bash`側のため）。→ **`/bin/bash` にフルディスクアクセスを付与**すれば常時起動でも取込を読める（要手動GUI・1回）。未付与でも他機能（検索・手入力登録・保管場所）は動く。取込セクションはOSErrorをcatchして案内表示。ターミナル由来で起動した場合はTerminalがFDAを持つため読める（＝切り分けの目安）。
- 個人情報（物件名・所在）を含み個人Dropboxも読むため、社内WiFi内のみ・認証なし公開である点に留意。

#### 「📄 PDFを整理」タブ（旧 pdf-organizer を統合・2026-08-09）

**クリアフォルダ1冊をまとめてスキャンした1つのPDF**を、書類1件ずつに**分割＋分類＋リネーム**する。
実体は `pdf_split.py`＋`ai_reader.py`。**単体CLIの `pdf-organizer` は役目を終えたので使わない**
（このリポジトリにも実体は無い）。判定結果はそのまま**中身の目録**になり、分割PDFは
種類別フォルダ入りのZIPで取り出せる。

- **役割分担**: 紙の原本の所在は「棚1-14」粒度で管理（本体機能） / こちらは**PDF化したデータ**を
  書類1件単位で整理。紙をPDF化しても原本は捨てられないので両方要る
- **AIはローカルの `claude` CLI**（APIキー不要）。テキスト層あり→**sonnet**、
  スキャン画像→**opus**（`ai_reader.TEXT_MODEL` / `VISION_MODEL`）。
  画像経路でsonnetは固有名詞を推測で置き換える実測があるため、ここは落とさないこと
- **長いPDFはウィンドウ分割**して判定する（`TEXT_WINDOW=30` ページ／`VISION_WINDOW=8` ページ。
  画像は1ページが高コストなので細かく刻む）。書類がウィンドウを跨いだ場合は
  `continues_from_previous` で結合する
- **ページの取りこぼし防止**（`_fill_gaps`）: AIが範囲を飛ばす／重複させても、
  1〜N全ページが必ずどれか1件に1回だけ入るよう後処理で補正。**出力からページが消えることはない**
- 和暦→西暦はプロンプトで指示（令和/平成/昭和 → `YYYY-MM-DD`）

### 不動産写真AI（photo-inpainter）補足 ※不動産・port 8506・完成（2026-08-10）

- 物件写真から**電柱・電線・通行人・車・室内の家具**を消すStreamlit。消去エンジンは **LaMa**、クリック選択は **Segment Anything (mobile_sam)**。どちらも **IOPaint（Apache-2.0・商用可）** の実装を`import`して使う。**全処理ローカル・APIキー不要**。
- モードは2つ。**🎯 AI選択**＝物体をクリックすると輪郭を自動抽出（点を足して範囲拡大／青クリックで除外）、**✏️ ブラシ**＝手動（電線など細いものはこちらが確実）。消去を**重ねがけ**でき、↩️元に戻す・複数枚アップロード・ZIP一括ダウンロードに対応。※Houghで電線を追跡する「電線クリック」モードも実装したが、実用性が薄く2026-08-10に削除済み（復活させないこと）。
- **⚠️ Intel Mac は torch==2.2.2 で固定必須（再調査不要）**。torch は **2.2.2 が macOS x86_64 向けの最終ビルド**で、2.3以降は arm64 ホイールしか公開されていない。`requirements.txt` でピン済み（arm64機でも2.2.2で問題なく動く）。
- **経緯（重要・同じ失敗を繰り返さないこと）**: 旧実装は `simple_lama_inpainting` を optional import していたが、これが **requirements.txt に一度も入っていなかった**ため `inpaint_lama()` は常に ImportError → `cv2.inpaint`（TELEA）へ暗黙フォールバックしていた。OpenCVは電線跡が茶色く滲むため「使えない」と判断され開発が止まっていた。**エンジン未導入が原因であってアルゴリズム選定の問題ではなかった。**
- モデルは初回実行時に `~/.cache/torch/hub/checkpoints` へ自動DL（`big-lama.pt` 約200MB / `mobile_sam.pt` 約40MB）。実測: 1600×1067 の電線消去が **CPUで約4秒**（長辺800px超は `HDStrategy.CROP` でマスク周辺だけ切り出して推論するため、原寸のまま高速かつマスク外は無劣化）。SAMは同一画像なら埋め込みを再利用し2回目以降 0.1秒。
- **SAMモデルは切替式**（mobile_sam / vit_b / vit_l / vit_h をサイドバーで選択）。既定は `default_sam_model()` が **MPSあり(Apple Silicon)→vit_b / なし(Intel)→mobile_sam** を自動判定。環境変数 `SAM_MODEL` で上書き可。**実測での注意（再検証不要）**: 軽バンを1クリックした場合 mobile_sam=選択14.2%/1.8s だが輪郭がギザギザで車体外にはみ出す、vit_b=選択5.6%/24.1s でスライドドア1枚を境界正確に選択。**大きいモデル＝広く取れる、ではない**。「意味のまとまり」で正確に切る方向に効くので、車1台なら追加クリック前提。
- `.venv`（1.3GB）と `samples/`（実物件の写真を含む）は**gitignore**。launchd登録済み（`com.shinsei.photo-inpainter`）・`run.sh` は不動産カテゴリのため `0.0.0.0` バインド。

### theta-viewer FTP APIサーバー port修正（2026-07-14）

- 旧: port 8519 → 新: **port 8523**。理由: 8519は`owner-payout-tracker`が既に使用しており実際は起動時にクラッシュしていた（KeepAliveで再起動ループ）。誰かが以前この衝突に気づき未コミットのまま8522に変更していたが、それはparking-map用に予約された番号と衝突するため、最終的に空きポート8523へ変更・再ビルド（`npm run build`→vite preview再起動）して確定。関連ファイル: `theta-viewer/server/server.js`（`const PORT`）、`theta-viewer/src/firebase.ts`（`API_BASE`）。

### 社内LAN常時起動ポート一覧（launchd / メインMac）

| port | アプリ名 | plist |
|---|---|---|
| 8503 | 見積書自動生成ツール | com.shinsei.quote-generator |
| 8504 | 物件管理案内文ジェネレーター | com.shinsei.property-notice-generator |
| 8505 | マイソクコンバーター | com.shinsei.maisoku-converter |
| 8506 | 不動産写真AI（インペインター） | com.shinsei.photo-inpainter |
| 8507 | 不動産・金融マスター電卓 | com.shinsei.realestate-calc |
| 8508 | 原状回復費用自動精算 | com.shinsei.restoration-calculator |
| 8509 | AI不動産価格査定 | com.shinsei.realestate-valuation |
| 8510 | 決済案内書自動作成 | com.shinsei.settlement-creator |
| 8511 | 間取り図トレーサー | com.shinsei.madori-tracer |
| 8512 | THETAパノラマ3D空間化 | com.shinsei.theta-viewer |
| 8513 | 特約条項ジェネレーター | com.shinsei.tokuyaku-generator |
| 8514 | 入金突合（消込）システム | com.shinsei99.payment-reconciler |
| 8515 | 物件写真一括リサイズ | com.shinsei.image-resizer |
| 8516 | 顧客追客マネージャー | com.shinsei.tsuikyaku-crm |
| 8517 | 媒介契約書ジェネレーター | com.shinsei.baikai-generator |
| 8519 | オーナー送金・月次締めマネージャー | com.shinsei.owner-payout-tracker |
| 8520 | 横断ファイル検索ブラウザ | com.shinsei.file-finder |
| 8521 | 業務マニュアル（Web） | com.shinsei.gyomu-manual |
| 8522 | 駐車場配置図ビューア | com.shinsei.parking-map |
| 8523 | theta-viewer FTP APIサーバー（server.js） | com.shinsei.theta-viewer-api |
| 8524 | 覚書・合意書ジェネレーター | com.shinsei.memorandum-generator |
| 8525 | 送付書メーカー | com.shinsei.soufu-maker |
| 8526 | 買取DMジェネレーター（※ツール・localhost・社内共有なし／常時起動のみ） | com.shinsei.kaitori-dm-maker |
| 8527 | PSA保有カード管理（※ツール・localhost・社内共有なし／常時起動のみ。Desktop/社内ツールに.appショートカット有） | com.shinsei.psa-collection |
| 8528 | 書類キャビネット（※不動産・社内LAN共有あり・0.0.0.0／要フルディスクアクセス for /bin/bash＝Dropbox取込読取） | com.shinsei.shorui-cabinet |
| 8529 | チラシクリエーター（※ツール・127.0.0.1・launchd未登録） | （未登録） |
| 8532 | マルチプロダクション（※不動産・開発中のため127.0.0.1・launchd未登録） | （未登録） |
| 8530 | AI業務マネージャー LINE webhook（※メインPCのみ稼働。ngrok固定ドメイン経由で公開） | com.shinsei.chatwork-ai-manager-line ＋ -ngrok |
| 8540 | AI業務マネージャー 管理画面（※不動産・0.0.0.0・パスワード認証あり） | com.shinsei.chatwork-ai-manager（worker は -worker） |
| 8600 | AI受付＆起票カウンター | com.shinsei.ai-ticket-counter |
| 5175 | 間取り図トレーサー 手動編集エディタ（editor/、Vite+React+TS） | com.shinsei.madori-tracer-editor |

### バインド先のルール（2026-08-07整合・必読）

**Streamlitは `--server.address` を省略すると既定が `0.0.0.0`（＝LANに公開）。「指定しなければlocalhost」ではない。** 実際にpsa-collection / kaitori-dm-makerが「localhostバインド」とコメントしながらLANへ公開されていた（保有明細・資産額を含むため要注意）。各`run.sh`は必ず明示すること。

| 分類 | バインド | 対象 |
|---|---|---|
| 不動産（社内LAN共有あり） | `--server.address 0.0.0.0` | 8503〜8525 の18本＋8528 shorui-cabinet＋8540 chatwork-ai-manager |
| 不動産だが**開発中** | `--server.address 127.0.0.1` | 8532 agent-platform（完成したら0.0.0.0へ） |
| ツール（社内共有なし） | `--server.address 127.0.0.1` | 8526 kaitori-dm-maker / 8527 psa-collection / 8529 flyer-creator / 3004 ai-tools-base（Next.js） |

確認は `lsof -nP -iTCP:<port> -sTCP:LISTEN`（`127.0.0.1:<port>` なら正しい。`*:<port>` は全公開）。

---

## ★ iOS App Store 再配信ルール（再発防止・必読）

**修正版を再アップロードするときは、必ずビルド番号（`CURRENT_PROJECT_VERSION`）を +1 する。**

> 2026-07-22の事故：photo-remake / neon-blocks とも、修正版を **build 1 のまま** 再アーカイブしていた。App Store Connect は「build 1 は既存」で新ビルドを受け付けず、**古い（修正前の）build 1 がそのまま審査を通り配信**されていた。ユーザーには「直したはずの不具合が残っている」状態に見えた。→ 両アプリを **1.0.1 / build 2** に繰り上げて解決。

### 再配信チェックリスト（Archive前に必ず）

1. `CURRENT_PROJECT_VERSION`（ビルド番号）を **既存の全アーカイブより大きい値**に +1 する
   - ネイティブ: `<app>.xcodeproj/project.pbxproj`（Debug/Release両方）＋ `project.yml`（xcodegen運用時）
   - Capacitor: `ios/App/App.xcodeproj/project.pbxproj`（※`ios/`はgitignore。`cap sync`しても番号は保持されるが、`cap add ios`でやり直すと1に戻る）
2. 必要なら `MARKETING_VERSION`（表示バージョン）も上げる（例 1.0.0 → 1.0.1）
3. **衝突チェック**: `./ios-build-guard.sh <app-folder>` を実行し「衝突なし」を確認（`--bump`で自動+1も可）
4. Capacitorは `npx cap sync` を実行してからArchive（`.xcworkspace`を開く）
5. Archive → Upload → App Store Connectで **今上げたbuild番号** が選択肢に出ることを確認してから提出
6. 配信物のソースは必ずコミット＆push（修正が手元だけに残ると同じ事故が再発する）

---

## Environment

- OS: macOS (darwin x86_64)
- Shell: zsh
- Custom binaries in `~/.local/bin` (added to PATH via `~/.zshrc`):
  - `gh` — GitHub CLI v2.94.0
  - `claude` — Claude Code CLI

## GitHub

Authenticated as **shinsei99** via `gh auth login`. The remote repository is `https://github.com/shinsei99/project` (public). Static HTML apps are published via GitHub Pages from the `gh-pages` branch (root), one folder per app, served at `https://shinsei99.github.io/project/<app>/`.

Common `gh` commands used in this repo:

```bash
gh repo view          # Show repository info
gh pr create          # Create a pull request
gh issue list         # List issues
```

## Git

```bash
git add <file>
git commit -m "message"
git push origin main
```
