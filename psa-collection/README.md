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
