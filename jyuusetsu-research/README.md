# AI重説調査 〜 Excel自動入力システム

不動産業務の「物件調査 → 登記簿解析 → 重説下調べ → Excelテンプレート自動入力」を
一気通貫で行う**調査支援・下書き生成**システム（Streamlit）。最終ゴールは宅建士が
確認できる「重要事項説明書ドラフト（Excel）」の自動生成。完全自動ではありません。

## 設計方針

- すべての情報は `models/property_data.py` の **PropertyData**（単一辞書）に集約。
- **入力 → 調査 → 整理 → 出力（Excel / PDF）** の一方向パイプライン。
- AI文章はテンプレート生成（OpenAI 等の有料LLMは不使用）。
- Google Maps は**座標の精度が上がるときだけ**使う（下の「ジオコーディングの選び方」）。
  キーが無いPCでは従来どおり国土地理院だけで動く。
- API失敗時もアプリは停止せず、空欄（「要確認」）で継続。

## 入力

1. 住所（必須）
2. 登記事項証明書（土地PDF）
3. 登記事項証明書（建物PDF）
4. 物件概要書PDF（任意・将来対応）

## 使用データ / API（すべて無料）

| 用途 | データ源 | キー |
|------|----------|------|
| ジオコーディング | 国土地理院 住所検索API（基本） | 不要 |
| ジオコーディング（精度が出るときだけ） | Google Geocoding | 直下 `.env.google-maps` |
| ストリートビュー（画面表示） | Google Street View Embed | 直下 `.env.google-maps` |
| 最寄駅・距離 | HeartRails Express API | 不要 |
| 周辺施設（学校/病院/スーパー/公園） | OpenStreetMap Overpass API | 不要 |
| 災害（ハザード確認導線） | 国土地理院 重ねるハザードマップ | 不要 |
| 用途地域/建ぺい率/容積率 | 国交省 不動産情報ライブラリ **XKT002** | 任意 `REINFOLIB_API_KEY` |
| 人口・世帯数 | e-Stat（政府統計） | 任意 `ESTAT_APP_ID` |

> 用途地域・人口は無料でもキー登録が必要なため、未設定時は空欄で継続します。

## 調べて分かったこと（次の担当が同じ調査を繰り返さないため）

### 用途地域は XKT002。XKT001 では**永久に空**（2026-08-20 修正）

不動産情報ライブラリのレイヤ番号を取り違えており、**キーは設定済みなのに用途地域が常に空**だった。

| | 誤 | 正（実測して確認） |
|---|---|---|
| エンドポイント | `XKT001`（＝都市計画区域・区域区分） | **`XKT002`**（用途地域） |
| 用途地域 | `youto_chiki` | `use_area_ja` |
| 建ぺい率 | `kenpei` に `%` を付ける | `u_building_coverage_ratio_ja`。**既に `"80%"`** なので付けない |
| 容積率 | `yoseki` に `%` を付ける | `u_floor_area_ratio_ja`。同上（`"60.0%"` の揺れは `60%` に正規化） |

- **防火地域・高度地区はこのAPIでは取れない**（XKT001〜XKT007 を実測。該当レイヤが無い）。
  空欄のまま返し、画面と重説ドラフトでは「都市計画図で要確認」として扱う
- 地点を含むポリゴンが無いとき、**最寄りポリゴンで代用してよいのは 100m 以内だけ**
  （`NEAR_LIMIT_M`）。上限が無いと、用途地域の定めが無い土地で **2.9km 先の地域**を返した
  （加東市・六甲山中の座標で実測）。重説ドラフトに入ると事故になる

### ジオコーディングの選び方 — Google に一本化しない（2026-08-20 実測）

`location_type` が **ROOFTOP / RANGE_INTERPOLATED のときだけ Google を採用**し、
それ以外は国土地理院を使う（`address_service.geocode_detail`）。

| 住所 | 地理院とGoogleのずれ | Google の精度 | 用途地域 |
|---|---|---|---|
| 大阪市中央区本町4-2-12 | 21m | ROOFTOP | 同じ |
| 千代田区丸の内1-1-1 | 62m | ROOFTOP | 同じ |
| 世田谷区北沢2-23-12 | 18m | ROOFTOP | 同じ |
| **兵庫県加東市社1** | **892m** | **APPROXIMATE** | **★違う（地理院が正しい）** |

画面には「座標: … （出典 Google(ROOFTOP)）」と出しているので、宅建士が精度を判断できる。

### ストリートビュー（未了・要 Console 設定）

`GOOGLE_MAPS_WEB_KEY` は **HTTPリファラが `https://daikyocorp.co.jp/*` に限定**されているため、
社内画面（`http://127.0.0.1:8599` 等）から Embed を開くと **403** になる（2026-08-20 実測。
撮影メタデータはサーバー用キーで取れるので「撮影時期 2021-08」は表示できている）。

**方針は「Embed 専用キーを新規作成」で決定（2026-08-20）。** 作り方:

1. Google Cloud Console（プロジェクト `daikyo-maps-2026`）→ 認証情報 → **APIキーを作成**
2. 名前は `maps-embed-internal` など
3. **「APIの制限」で `Maps Embed API` **だけ**を選ぶ**（ここが肝。Embed は無制限・無料なので、
   このキーは**どう使われても課金が発生しない**）
4. 「アプリケーションの制限」はリファラでも「なし」でもよい。社内画面はポートが変わるので、
   リファラにするなら `http://localhost:*/*` `http://127.0.0.1:*/*` `http://192.168.1.105:*/*` を許可
5. できたキーを直下 `.env.google-maps` に **`GOOGLE_MAPS_EMBED_KEY=...`** として追記する

コード側は対応済み（`google_maps_api.embed_key()` が `GOOGLE_MAPS_EMBED_KEY` →
無ければ `GOOGLE_MAPS_WEB_KEY` の順で使う）。**キーを1行足すだけで表示される。**
- **規約**: ストリートビューは**印刷物に一切使えない**（チラシ・DM・重説の紙面は不可）。
  Google以外の地図と同一画面に並べない（この画面はハザードマップを"リンク"で置くだけ）

## セットアップ / 起動

```bash
cd jyuusetsu-research
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# （任意）取得項目を増やす場合
export REINFOLIB_API_KEY=...   # 用途地域
export ESTAT_APP_ID=...        # 人口・世帯数

streamlit run app.py --server.port 8512
```

## 出力

- 画面表示（基本情報 / 都市計画 / 災害 / 周辺環境 / 登記 / AIコメント）
- Excel: `reports/jyuusetsu_draft.xlsx`（重説テンプレートにセルマッピング書き込み）
- PDF: `reports/jyuusetsu_draft.pdf`（reportlab・日本語対応）

## 実書式テンプレートへの流し込み（重要）

実際の重説書式（Excel）へ `PropertyData` を流し込めます。書式は
`services/format_export_service.py` の `FORMATS` に登録し、`{項目: セル}` の
マッピングで書き込みます。**新しい書式は FORMATS に 1 エントリ足すだけ**。

対応済み書式:

| キー | 書式 | テンプレート | 流し込み項目 |
|------|------|--------------|--------------|
| `rental_building` | 賃貸重説（建物賃貸借用 A4） | `templates/rental_building_template.xlsx` | 所在地→L90/L92、床面積→Y100、所有者→L106 |
| `sale_landbuilding` | 売買契約書（土地建物・公募用 一般売主） | `templates/sale_landbuilding_template.xlsx` | 所在地→D10/H18、地番→W10、地目→AF10、地積→AL10/AL15、家屋番号→AN18、種類→H19、構造→X19、床面積(延床)→AN21、所有者(売主)→D5 |
| `sale_mansion_contract` | 売買契約書（区分所有建物・敷地権 宅建業者売主） | `templates/sale_mansion_contract_template.xlsx` | 所在地→I8/H16、地番→Z16、地目→AK16、地積→AT16、家屋番号→I12、種類→AT12、構造→I13、床面積(専有)→AT13 |
| `sale_mansion_jyuusetsu` | 重要事項説明書（区分所有建物の売買・交換用） | `templates/sale_mansion_jyuusetsu_template.xlsx` | 所在地→M58/F77、地番→V77、地目→AD77、地積→AO77、家屋番号→M62、種類→M63、構造→M64、床面積(登記簿)→AD66 |

- 賃貸（建物賃貸借）は登記記録に基づく **所在地・床面積・所有者** を下書き。
  法令制限・災害・ライフライン等のチェック欄は自動判定値を持たないため既定のまま。
- 売買（土地建物）は「（A）売買の目的物の表示」へ **所在地・地番・地目・地積・家屋番号・
  種類・構造・床面積・所有者(売主)** を下書き。代金・期日・数式セルは変更しない。
- **無損失書き込み**: `services/xlsx_patcher.py` が編集対象シートの XML だけを
  書き換え、図形・画像・他シート（表紙等）は元ファイルからバイト単位でコピーします。
  openpyxl の再保存と異なり図形が欠落しません。空の項目はテンプレ既定値を保持します。

### 汎用ドラフトテンプレート

書式を指定しない汎用ドラフトは `templates/jyuusetsu_template.xlsx`（無ければ自動生成）。
セル位置は `services/excel_export_service.py` の `CELL_MAP`（項目→行番号）で調整します。

## フォルダ構成

```
jyuusetsu-research/
  app.py
  services/  address / zoning / hazard / facility / population / registry / comment / excel_export / pdf_export
  models/    property_data.py
  utils/     parser.py / formatter.py
  templates/ jyuusetsu_template.xlsx（自動生成）
  reports/   出力先
  data/
```

## 将来拡張（設計上の差し込み口）

接道情報 / 上下水道・ガス / 景観条例 / 35条書面生成 / 契約書ドラフト / LLM文章生成。
いずれも PropertyData にフィールドを足し、対応サービスを追加するだけで拡張できます。
