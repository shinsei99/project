# PSA保有カード管理

PSA「My Collection」のCSVエクスポートを読み込み、**保有カードの検索・絞り込み・保管場所の記録**を行う在庫管理アプリ。

- 形式: Streamlit
- port: **8527**
- カテゴリ: ツール（社内LAN共有なし・launchd未登録）

## 起動

```bash
./run.sh
```

初回のみ `.venv` を作成して依存パッケージを入れます。起動後 http://localhost:8527 。

## データ

| パス | 内容 |
|---|---|
| `data/collection.csv` | PSA My Collection のエクスポートCSV（そのまま） |
| `data/storage_notes.json` | 保管場所・メモ（証明書番号がキー） |
| `data/images/<証明書番号>.jpg` | カード画像（`_back.jpg` は裏面） |
| `data/thumbs/<証明書番号>.jpg` | 一覧表示用サムネイル（初回表示時に自動生成） |
| `data/image_urls.json` | PSA側の画像URL（ローカル保存に失敗した場合の直リンク用） |
| `data/image_state.json` | API呼び出しの当日カウント・取得失敗記録 |
| `data/psa_api.json` | PSA APIトークン |

`data/` は**gitignore対象**。保有明細と資産額を含むため公開リポジトリには出しません。

### CSVの更新

サイドバー「📥 データ更新」から新しいエクスポートCSVをアップロードすると丸ごと差し替わります。
保管場所メモは証明書番号にひも付いて別ファイルに保存されるため、差し替えても消えません。

## カード画像

「どれを保有しているか」を絵で確認するための機能。画像は**証明書番号ごとにローカルへ永久キャッシュ**され、一度取得したものは再取得しません。

**取得済み: 871枚（保有381＋売却済490）／ 443MB。** 下の「app.collectors.com から取得」の方法で全件揃っています。

### app.collectors.com から取得（実際に使えた方法）

PSA公開APIは承認制で403になるため、**ログイン済みブラウザのセッションでPSAサイト内部のAPIを叩く**のがこのアプリの取得ルート。承認も回数制限も不要で、871枚を数分で取得できる。

1. Safari設定 > 詳細 > 「Webデベロッパ用の機能を表示」→ 開発メニュー > 「Apple EventsからのJavaScriptを許可」
2. https://app.collectors.com/collection/ を開いてログイン
3. `harvest_collectors.js` をページに流し込む（手順はファイル冒頭のコメント参照）
4. 集めた結果をJSONLにして `python3 import_from_web.py <file.jsonl>`

内部APIの構造:

| 呼び出し | 役割 |
|---|---|
| `collection.list` | カード一覧。`cursor`=ページ番号、`pageSize`=件数、`totalItems`=総数。**画像URLはnull** |
| `collection.images` | listの結果を渡すと `collectibleId` をキーに `original/large/medium/small/thumbnail` を返す |

入力は `{"0": "<JSONを16進エンコードした文字列>"}` という形式。画像実体は `d1htnxwo4o0jhw.cloudfront.net` にあり**認証不要**で落とせる。

一覧表示用のサムネイル（幅420px）は初回表示時に `data/thumbs/` へ自動生成される。

### PSA公開APIから自動取得（※現状は使えない）

> **2026-08-05時点で403。** トークンは正しく発行・認識される（無効トークンなら429、有効だと403）が、
> `{"Message":"Access to this API is limited to approved customers."}` が返り、アカウントの利用承認が必要。
> 申請窓口はページ上に無く `collectors-apis@collectors.com` のみ（依頼文の下書きは `api_access_request.md`）。
> 承認が下りればコード変更なしで下記がそのまま動く。

1. https://www.psacard.com/publicapi でPSAアカウントにログインし、**APIトークンを無料発行**
2. サイドバー「🖼 カード画像の取得」にトークンを貼る（`data/psa_api.json` に保存）
3. 「▶ N枚 取得する」を押す

**無料枠は1日100件**。上限に達すると自動で停止するので、翌日また押せば続きから取得します。
保有381枚なら **4日で全部揃う** 計算です。当日の残り回数は画面に出ます。

> PSAの証明書ページ（psacard.com/cert/…）自体はCloudflareで保護されておりスクレイピングできません。自動取得はこのAPI経由のみです。
> 画像ファイルのダウンロードに失敗した場合も画像URLは控えておき、ブラウザから直接表示します。

### 手動で入れる

自分で撮影・スキャンした画像も使えます。ファイル名を証明書番号（`98769002.jpg` / 裏面は `98769002_back.jpg`）にして、サイドバー「📷 画像を手動で追加」からアップロード。件数制限なし。

## 機能

**🖼 ギャラリータブ**
- カード画像をグリッド表示。グレード・金額・カード名・保管場所を添えて、見た目で保有カードを確認
- **並べ替え**（PSA推定額／年／グレード／セット／カード名、売却済なら売却日・売却額も）
- 1行の枚数／1ページの枚数／ページ送りを調整可。「拡大」で原寸表示
- 絞り込みの「カード画像」で「画像ありのみ / 画像なしのみ」に切替（未取得の洗い出しに使う）

**サイドバー（絞り込み）**
- 保有中 / 売却済 / すべて の切替
- キーワード検索（カード名・セット名・品名・証明書番号・保管場所・メモを横断、スペース区切りAND）
- グレード、セット（件数付き）、年、Vault状況、出品状況、PSA推定額のレンジ
- 「保管場所が未記入のものだけ」

**📋 一覧タブ**
- 並べ替え可能な一覧。`PSA` 列のリンクから psacard.com の証明書照会ページへ
- 絞り込み結果をCSVダウンロード

**📦 保管場所タブ**
- 現物がどこにあるか（バインダーA / 金庫 / PSA Vault など）とメモを直接編集して保存

**📊 集計タブ**
- セット別・グレード別・年別の枚数と金額、上位30枚

## 元データの注意点

- `My Cost`（取得原価）`My Value` `Date Acquired` `Source` `My Notes` はPSA側で全件空欄。
  そのため損益は「売却額 − 手数料 = 手取り」までしか出せず、仕入値ベースの利益は算出できません。
- `Year` に `1998-99` 形式が混じる（ANCIENT MEW 4件）。先頭4桁を数値の年として扱っています。
- 売却済カードは `Vault Status` が空欄。Vault集計は保有中が対象です。

## 別PCへの引き継ぎ

**画像443MBを運ぶ必要はありません。** CloudFrontの画像URLは認証不要なので、URLリストさえあれば落とし直せます。

引き継ぐファイル（`data/` 配下、合計約330KB）:

| ファイル | 中身 |
|---|---|
| `collection.csv` | PSA My Collection エクスポート |
| `image_urls.json` | 871枚ぶんの画像URL ← **これが画像の実体を兼ねる** |
| `storage_notes.json` | 保管場所メモ |

受け取り側の手順:

```bash
git pull                            # アプリ本体
# 上記3ファイルを psa-collection/data/ に置く
cd psa-collection
python3 import_from_web.py          # 871枚をCloudFrontから自動ダウンロード
./run.sh                            # http://localhost:8527
```

サムネイル（`data/thumbs/`）は初回表示時に自動生成されるので運ぶ必要はありません。

## 運用メモ（ルート CLAUDE.md から移動・2026-08-17）

> 元の見出し: 「PSA保有カード管理（psa-collection）補足 ※ツール・port 8527」
> **他PCと共有される情報。** ここを直せば2台で同じ内容になる。

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
