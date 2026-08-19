# Google Maps Platform — 導入前の裏取り（2026-08-19・サブPCで調査）

**まだ契約していない。キーも取っていない。** 導入するかどうかを決めるために、
**料金体系と利用規約を一次情報（Google公式）で確認した記録**。

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

## 4. 導入するならこの順

1. **Demo Key で `jyuusetsu-research` に別タブでストリートビューを出す**
   （社内画面のみ＝公開課金なし、印刷しない＝規約リスクなし、代替不可能な価値）
2. 手応えがあれば通常キーへ（**ここで初めてカード登録**）
3. 物件サイト（`flyer-creator` → FTP）に Embed で地図＋ストリートビュー
4. 紙チラシの案内図（Maps Static＋帰属表示。**部数5,000を超えない**運用を決めてから）

### キーの置き場（着手時に守ること）

- **フロントに出るキー**（Embed / Maps JS）は **HTTPリファラ制限**を必ずかける。
  物件サイトは FTP で `daikyocorp.co.jp` に上がる**公開物**なので、キーがHTMLに残る
- **サーバー側キー**（Geocoding / Places / Directions）は **IP制限**
- 置き方はこのリポジトリの流儀に乗せる: `.env` を gitignore ＋ `./secrets-sync.sh` で2台に配る

---

## 出典（すべて2026-08-19に確認）

- 料金: https://developers.google.com/maps/billing-and-pricing/pricing
- 2025年3月の変更: https://developers.google.com/maps/billing-and-pricing/march-2025
- 利用規約: https://cloud.google.com/maps-platform/terms
- サービス個別規約: https://cloud.google.com/maps-platform/terms/maps-service-terms
- Geo Guidelines（印刷物）: https://about.google/brand-resource-center/products-and-services/geo-guidelines/
- Maps JS ポリシー（帰属表示）: https://developers.google.com/maps/documentation/javascript/policies
- Demo Key: https://mapsplatform.google.com/maps-demo-key/
