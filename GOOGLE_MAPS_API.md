# Google Maps Platform — 裏取りと取得の記録（2026-08-19・サブPC）

**2026-08-19 に取得済み。** 下の「取得の記録」を見ること。
本文は、導入を決める前に**料金体系と利用規約を一次情報（Google公式）で確認した記録**。

---

## 取得の記録（2026-08-19・サブPCで実施）

| 項目 | 値 |
|---|---|
| Cloud プロジェクト | **`daikyo-maps-2026`**（表示名 Daikyo Maps） |
| 請求先アカウント | `019EA9-7BA976-F67AF2`（**Gemini と同じカード。再入力なしで流用した**） |
| ログイン | `daikyocorp.s@gmail.com` |
| 有効化したAPI | Maps Embed / Street View Static / Geocoding / Directions / Maps Static ＋ **Drive API** |
| キーの置き場 | **`.env.google-maps`（直下・gitignore・パーミッション600）**。`secrets-manifest.txt` に登録済み＝`./secrets-sync.sh` で2台に渡る |

**発行したキーは2本。用途で分けてある。**

| 変数名 | 制限 | 使うAPI |
|---|---|---|
| `GOOGLE_MAPS_WEB_KEY` | **HTTPリファラ `https://daikyocorp.co.jp/*`** | Maps Embed / Maps Static |
| `GOOGLE_MAPS_SERVER_KEY` | **API種別で制限**（IP制限は未設定・下記） | Geocoding / Directions / Street View Static / Maps Static |

**動作確認済み**（2026-08-19・実際に叩いた）:

- Geocoding … 「大阪市中央区本町4-2-12」→ `status: OK` / 34.6833416, 135.5001744
- Street View metadata … 同座標に **2021-08 撮影のパノラマあり**（`status: OK`）

### ★ なぜ Gemini とは別プロジェクトなのか（最重要）

Google のAPIキー（`AIza…`）は、**プロジェクトで Generative Language API（Gemini のバックエンド）が
有効になっていると、そのプロジェクトの既存キー全部が Gemini エンドポイントにも通る**仕様になっている。
キーを作り直さなくても、黙って権限が増える。

Maps のキーは**公開HTMLに載る**（物件サイトはFTPで `daikyocorp.co.jp` に上がる公開物）。
同じプロジェクトで取っていたら、**誰でも読めるキーで Gemini を叩かれ、請求は同じカードに乗っていた。**

→ **`daikyo-maps-2026` では Generative Language API を絶対に有効化しない。**
Gemini 側（`Default Gemini Project`）にも Maps を足さない。

### 残っている宿題

- **サーバー用キーにIP制限がかかっていない**（事務所の固定グローバルIPが不明なため）。
  IPが分かり次第 `gcloud services api-keys update` で足すこと。
  当面の安全弁は「このプロジェクトに Gemini が無いこと」＋「API種別の制限」
- **予算アラートと日次クォータ上限が未設定。** 同じカードに Gemini と相乗りしているので、
  Maps 側が暴走すると合算で請求が来る
- **Drive API は有効化しただけ**。実際に使うには OAuth クライアント（同意画面）の設定が別途要る

結論を一行で言うと —
**「画面で見る」用途はほぼ無料・制約なし。「保存する・印刷する・AIに読ませる」用途は規約で塞がれている。**

対象アプリ: `jyuusetsu-research` / `flyer-creator` / `realestate-valuation` /
`legal-crosscheck` / `kaitori-dm-maker` / `parking-map`。

---

## 0. 先に知っておくこと — 既存の無料APIで足りている部分がある

**ジオコーディング（住所→緯度経度）と最寄駅は、すでに無料・キー不要で動いている。**
ここに課金する意味はない。

| 実装 | 使っているAPI |
|---|---|
| `realestate-valuation/services/geo_service.py` | 国土地理院 AddressSearch / LonLatToAddress |
| `jyuusetsu-research/services/address_service.py` | 国土地理院 ＋ HeartRails Express（最寄駅） |
| `legal-crosscheck/services/geo_service.py` | 同上 |

`address_service.py` の冒頭には「有料 API / Google Maps API は使用しない」と明記してある。
**Google に払う価値があるのは、下の「Googleでしか取れないもの」だけ。**

| 取れるもの | 代替 |
|---|---|
| **ストリートビュー**（外観・前面道路の目視） | **代替なし。これが本命** |
| Places（スーパー・学校・病院を実名で） | HeartRails は駅のみ＝取れない |
| Directions（**道路距離**の徒歩分数） | 直線距離しかない。表示規約は道路距離80m＝1分 |
| Static Maps（案内図の画像） | 地理院タイルで代替可。見慣れているだけの差 |

---

## 1. キーの取得にクレジットカードは要るか

| 種類 | カード | 用途 |
|---|---|---|
| **Maps Demo Key** | **不要**（Googleアカウントだけ） | 試作・評価用。**APIごとに日次上限**があり、超えると地図がその日は止まる（課金はされない）。**本番不可** |
| 通常のAPIキー | **必要**。請求先アカウントを有効にしないとキーが出ない | 本番。無料枠内なら請求は発生しない |

- 新規は **$300 のウェルカムクレジット**（90日または使い切りまで）が付く場合がある
- Demo Key が対応するもの: Dynamic Maps / Places UI Kit / 3D Maps / Weather /
  Compute Routes / Autocomplete / Text Search / **Geocoding** など
  （**Street View Static は一覧に無い**＝本命の検証には通常キーが要る可能性が高い。**未確認**）

→ **まず Demo Key で触ってみて、続ける判断がついてからカードを登録する**のが順序として無駄がない。

---

## 2. 料金（2025年3月1日〜の新体系）

**旧「$200/月クレジット」は廃止**され、**APIごとの月次無料枠**になった。**枠は合算されない**
（Essentials 10,000 / Pro 5,000 / Enterprise 1,000 が基本の刻み）。

| API | 無料枠/月 | 超過分 |
|---|---|---|
| **Maps Embed / Street View Embed** | **無制限・無料** | — |
| Maps Static（地図画像） | 10,000 | $2.00 / 1,000 |
| Street View Static（画像） | 5,000 | $7.00 / 1,000 |
| Geocoding | 10,000 | $5.00 / 1,000 |
| Directions / Distance Matrix | 10,000 | $5.00 / 1,000 |
| Place Details | 10,000 | $5.00 / 1,000 |
| **Places Nearby Search** | 5,000 | **$32.00 / 1,000**（突出して高い） |
| Maps JavaScript 動的地図 | 10,000 | $7.00 / 1,000 |

**実質コストの見積もり: ほぼ $0。** 社内利用で月50物件を扱っても、全API合わせて数百コールで
無料枠に収まる。

**重要: 埋め込み（Embed）は無制限無料。** したがって公開中の物件サイト
`daikyocorp.co.jp/slowlife/` に地図やストリートビューを載せても、**訪問者数で課金されない**。
課金されるのは Maps JavaScript（動的地図）を自前で組んだ場合。

---

## 3. 規約 — できること・できないこと

出典は Maps Platform 利用規約 3.2.3 / Maps Service Specific Terms / Geo Guidelines。

### ✕ できない（明確に禁止）

| やろうとしたこと | 該当条項 |
|---|---|
| **航空写真をなぞって駐車場配置図を作る**（`parking-map` 案） | 3.2.3(c)(i) "trace or **digitize** roadways, building outlines … from the **Satellite** base map type" |
| **ストリートビュー画像をAIに読ませて空き家判定**（`kaitori-dm-maker` 案） | 3.2.3(c)(vii) "use Google Maps Content **to improve machine learning and artificial intelligence models**, including to train, test, validate or fine-tune" |
| **ストリートビュー画像を紙のチラシ・DMに印刷する** | Geo Guidelines "Street View imagery **may not be used for any print purposes**" |
| **画像をダウンロードして保存し、重説PDFやDMに焼き込む** | 3.2.3(a) No Scraping "pre-fetch, index, store, reshare, or **rehost**" |
| ストリートビューと**非Googleの地図を同じ画面に**並べる | 3.2.3(e)(ii) "display Street View imagery and non-Google Maps **on the same screen**" |

> AI条項について: 条文は「モデルの**改善**（学習・テスト・検証・微調整）」を禁じており、
> 単なる推論が該当するかは条文上グレー。ただし画像を Claude / Gemini の API に送った時点で
> 送信先での扱いを保証できないため、**やらない**と判断した。

> 既存アプリへの影響: `jyuusetsu-research` / `legal-crosscheck` は国土地理院・ハザードマップを
> 画面に出している。**ストリートビューを足すなら別タブ・別画面に分ける**こと。

### ○ できる（条件つき）

| やりたいこと | 条件 |
|---|---|
| 画面上でストリートビューを見る | Embed なら無料無制限。保存しない |
| 物件サイトに地図・ストリートビューを埋め込む | 同上。帰属表示は消さない |
| 徒歩分数を道路距離で出す | Directions。無料枠内 |
| **紙のチラシに案内図（地図）を載せる** | **5,000部まで**（案内目的の販促物）／業務文書（報告書・提案書）は可。**帰属表示（Googleロゴまたは "Google Maps" の文字）必須・改変不可**。**ストリートビューは不可** |

### 保存してよいもの／だめなもの

| データ | 保存期間 |
|---|---|
| `place_id`（Places/Directions/Routes）、`pano_ID`（Street View Static） | **無期限** |
| Geocoding の緯度経度 | 原則 **30日**。ただし「そのリクエストを出したアプリの、エンドユーザー向け機能を直接支える」用途なら **無期限**（Service Terms 6.3.2） |
| **Places の緯度経度** | **30日のみ**（14.3）。6.3.2 のような無期限の例外は無い |
| 地図画像・ストリートビュー画像 | **保存不可**（都度APIから表示する） |

---

## 4. 使う順（キーは取得済みなので、あとは組み込むだけ）

1. **`jyuusetsu-research` に別タブでストリートビュー**
   （社内画面のみ＝公開課金なし、印刷しない＝規約リスクなし、代替不可能な価値）← 次の一手
2. 物件サイト（`flyer-creator` → FTP）に Embed で地図＋ストリートビュー（`GOOGLE_MAPS_WEB_KEY`）
3. 徒歩分数を道路距離に（Directions・`GOOGLE_MAPS_SERVER_KEY`）
4. 紙チラシの案内図（Maps Static＋帰属表示。**部数5,000を超えない**運用を決めてから）

### 組み込むときに守ること

- 読み込みは `.env.google-maps` から。**コードにキーを直接書かない**
- 公開ページに出すのは **`GOOGLE_MAPS_WEB_KEY`（リファラ制限つき）だけ**。
  サーバー用キーを HTML に出さない（API種別の制限しか掛かっていない）
- 帰属表示（Googleロゴ／"Google Maps" の文字）を消さない・改変しない

---

## 出典（すべて2026-08-19に確認）

- 料金: https://developers.google.com/maps/billing-and-pricing/pricing
- 2025年3月の変更: https://developers.google.com/maps/billing-and-pricing/march-2025
- 利用規約: https://cloud.google.com/maps-platform/terms
- サービス個別規約: https://cloud.google.com/maps-platform/terms/maps-service-terms
- Geo Guidelines（印刷物）: https://about.google/brand-resource-center/products-and-services/geo-guidelines/
- Maps JS ポリシー（帰属表示）: https://developers.google.com/maps/documentation/javascript/policies
- Demo Key: https://mapsplatform.google.com/maps-demo-key/
