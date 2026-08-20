# API の棚卸しと段取り（2026-08-19 作成 / **2026-08-20 サブPCで更新**）

**この1枚から再開できるようにしてある。**

> **2026-08-20 に進んだこと**
> - **日本郵便が本番になった**（本番の資格情報を受領・差し替え・疎通確認済み。B-1 参照）
> - **用途地域のバグ（不具合①）を修正**。ついでにジオコーディングを Google 併用にした
> - **ストリートビューを `jyuusetsu-research` に組み込んだ**が、Webキーのリファラ制限で
>   社内画面からは 403（**Console 設定が要る＝人の作業**。下の A-2 ⑦-b）

- Google Maps の料金・規約の詳細 … `GOOGLE_MAPS_API.md`
- 日本郵便のコード … 直下 `japanpost_api.py`
- 進行中タスクの索引 … `TODO.md` の「横断作業」

---

## A. 明日の段取り（この順が無駄がない）

### A-1. 人にしかできない（朝いちで出す。待ち時間があるもの優先）

| # | やること | 所要 | なぜ先か |
|---|---|---|---|
| 1 | **国税庁 法人番号 Web-API の申請** | 5分 | **発行に2週間〜1か月**。出さないと待ちが始まらない |
| 2 | **e-Stat の appId 登録**（https://www.e-stat.go.jp/api/ ） | 5分 | 無料。メール本人確認があるので本人操作 |
| ~~3~~ | ~~日本郵便の本番申込~~ | — | **✅ 2026-08-20 完了**（本番の資格情報を受領して差し替え済み） |
| 4 | **App Store Connect の APIキー（.p8）作成** | 5分 | 追加費用なし・審査待ちなし |

**1 の文面（このまま送れる）** — 先にフォーム
（https://www.invoice-kohyo.nta.go.jp/web-api/index.html#cmsprereg ）を出してから
`invoice-web-api@nta.go.jp` へ:

```
件名: 法人番号システムWeb-API アプリケーションID発行届出について

国税庁 軽減税率・インボイス制度対応室 御中

アプリケーションID発行届出フォームより届出を行いましたので、
下記のとおりご連絡いたします。

・利用者の名称: 大京商事株式会社
・メールアドレス: daikyocorp.s@gmail.com
・法人番号システムWeb-APIのみ利用を希望します

用途: 自社業務システムにおける取引先法人情報の照合・入力補助

大京商事株式会社
担当: 鷲見
電話: 06-6353-0418
```

### A-2. Claude 側でできる（資格情報が来たら、または今すぐ）

| # | やること | 前提 |
|---|---|---|
| ~~5~~ | ~~`zoning_service.py` の `XKT001` → `XKT002` 修正~~ | **✅ 2026-08-20 完了**（プロパティ名・単位・最寄り代用の上限まで直した） |
| 6 | **e-Stat の実装を書く**（いまは空を返すだけ。下の不具合②） | appId が要る |
| 7 | サーバー用 Maps キーに **IP制限**を足す | 事務所のグローバルIPが要る |
| 8 | **予算アラート・日次クォータ**の設定（Gemini と同じカードなので合算請求になる） | — |
| ~~9~~ | ~~`jyuusetsu-research` にストリートビューを組み込む~~ | **✅ 2026-08-20 実装**（ただし下の ⑦-b が残っている） |
| **7-b** | **Webキーのリファラ制限で社内画面が 403**。`https://daikyocorp.co.jp/*` しか許可されていない。**推奨: Maps Embed だけに絞ったキーを新規作成**して社内画面用にする（埋め込みは無制限無料なので漏れても課金されない） | **Console 作業＝人がやる** |

---

## B. いま持っているAPI（棚卸し・値は書かない）

### B-1. 2026-08-19 に取得したもの

| API | 保管先 | 変数名 | 状態 |
|---|---|---|---|
| **Google Maps / Street View** | `.env.google-maps` | `GOOGLE_MAPS_WEB_KEY` / `GOOGLE_MAPS_SERVER_KEY` | ✅ **本番・動作確認済み** |
| **日本郵便 デジタルアドレス** | `.env.japanpost` | `JAPANPOST_CLIENT_ID` / `_SECRET_KEY` | ✅ **本番・動作確認済み**（2026-08-20 差し替え）。`JAPANPOST_HOST` の行は消した＝本番に向く。テスト用stubは `.env.japanpost.bak-stub` に退避 |

- 日本郵便は **`searchcode "100"` がテスト用では2件、本番では466件**返る（＝実データかどうかの判別に使える）
- Maps のプロジェクトは **`daikyo-maps-2026`**。請求先は Gemini と同じ口（カード再入力なし）
- **★このプロジェクトで Gemini(Generative Language API) を絶対に有効化しない。**
  有効にすると**同じプロジェクトの全APIキーが Gemini にも通る**ため、公開ページに載せた
  Maps キーで Gemini を叩かれ、同じカードに請求が乗る（理由の詳細は `GOOGLE_MAPS_API.md`）

### B-2. 以前から持っているもの

| 種別 | キー名 | 置き場 |
|---|---|---|
| AI | `ANTHROPIC_API_KEY` | `agent-platform/.env`, `madori-tracer/.env.local` |
| AI | `GEMINI_API_KEY` | `agent-platform/.env`, `brain-dump/.env.local`, `pasha-calo/.env.local` |
| AI | `OPENAI_API_KEY` / `GROQ_API_KEY` / `STABILITY_API_KEY` | `agent-platform/.env` |
| 音声・素材 | `ELEVENLABS_API_KEY`(+`VOICE_ID`) / `PEXELS_API_KEY` | `agent-platform/.env` |
| 不動産 | `reinfolib_api_key` | `jyuusetsu-research` / `realestate-valuation` / `legal-crosscheck` の `.streamlit/secrets.toml` |
| 公開 | FTP（`host`/`user`/`pass`/`root`） | `theta-viewer/server/ftp-config.json` |
| その他 | Supabase / `DATABASE_URL` / 各種 `ACCESS_CODE`・`.stats_key`・`.secret_key` | 各アプリ |
| GitHub | `gh` CLI（keyring・shinsei99） | — |

**このサブPCに無いもの（正常）**: Chatwork / LINE のトークン
（`CHATWORK_API_TOKEN` ほか）。常駐はメインPCのみで、専用の `handoff_export.sh` で運ぶ設計。

### B-3. 未取得

| API | 状態 | 費用 |
|---|---|---|
| 国税庁 法人番号 | 未申請（**発行2週〜1か月**） | 無料・添付書類なし |
| インボイス公表システム | 未申請（申請書＋添付資料が要る） | 無料 |
| e-Stat | 未登録 | 無料 |
| App Store Connect | 未作成（.p8を作るだけ） | 追加費用なし |
| Google Drive | **有効化済み**だが OAuth 同意画面が未設定 | 無料 |

---

## C. 見つかった不具合（新しいAPIを取るより先に効く）

### ①【✅ 2026-08-20 修正済み】用途地域が取れていない — `jyuusetsu-research/services/zoning_service.py`

`XKT001` を叩いているが、用途地域は **`XKT002`** が正しい。
`legal-crosscheck/services/admin_research_service.py:154` は正しく `XKT002` を使っている。
**キーは3アプリとも持っているのに、機能だけ死んでいる。**

**実際に直してみると1行では済まなかった**（2026-08-20・実測してから直した）:

- 読んでいたプロパティ名も別レイヤのものだった（`youto_chiki` → **`use_area_ja`**、
  `kenpei`/`yoseki` → **`u_building_coverage_ratio_ja`/`u_floor_area_ratio_ja`**）
- 建ぺい率・容積率は **`"80%"` と単位付きで返る**ので `%` を足すと `80%%` になる
- **防火地域・高度地区はこのAPIに無い**（XKT001〜007 を実測）。空欄＝要手動確認で確定
- 移植元にあった「最寄りポリゴンで代用」は、上限が無いと **2.9km 先の用途地域**を返す
  （加東市で実測）。100m の上限を付けた

詳細と実測値は `jyuusetsu-research/README.md`。

### ② e-Stat は「呼ぶコードが無い」 — `jyuusetsu-research/services/population_service.py:44`

`ESTAT_APP_ID` が未設定なのは事実だが、**設定しても直らない**。
関数は地域名を抽出したあと、APIを呼ばずに空の辞書を返している（コメントに「導線のみ用意」）。

実装の山は**地域コードの解決**（e-Stat は `statsDataId` ＋ `cdArea` 指定）。
ただし部品は既にある — `realestate-valuation/services/geo_service.py` の
国土地理院 逆ジオコーディングが**緯度経度→市区町村コード**を返す。
住所 → 緯度経度 → 市区町村コード → e-Stat と繋げばよい。

---

## D. 規約で「やらない」と決めたこと（蒸し返さないための記録）

| やろうとした案 | 不可の理由 |
|---|---|
| `parking-map` で航空写真をなぞって配置図を作る | Maps規約 3.2.3(c)(i) トレース・デジタル化の禁止 |
| `kaitori-dm-maker` でSV画像をAIに読ませて空き家判定 | 3.2.3(c)(vii) AIモデルへの利用禁止 |
| 紙のチラシ・DMにストリートビューを印刷 | Geo Guidelines「SVは印刷用途に一切使えない」 |
| SVと地理院地図・ハザードマップを同一画面に表示 | 3.2.3(e)(ii)。**別タブに分ければ可** |

**やってよい**: 画面でSVを見る（Embedは無料無制限）／物件サイトへの埋め込み／道路距離の徒歩分数／
**紙チラシの案内図（地図は5,000部まで・帰属表示必須）**。

---

## E. 検討中（まだ取っていない・判断待ち）

| 候補 | 効く先 | 状態 |
|---|---|---|
| **App Store Connect API** | `ios-build-guard.sh` を**実際の登録済みビルド番号**で判定できる（2026-07-22の再配信事故の根本対策）。審査状況の確認も | 追加費用なし。**推し** |
| **Dropbox API** | `shorui-cabinet/inbox.py` がローカル同期フォルダを読む方式 → `/bin/bash` にフルディスクアクセスを与えている回避策を廃止できる | 無料 |
| 銀行API / freee・MF | `payment-reconciler/app.py:52` は**銀行CSVを手でアップロード**。API化で前工程が消える | **未確認**（取引銀行がどこかで変わる） |
| Google Document AI | `handwriting-ocr` は Claude CLI に手書きPDFを渡す方式。精度比較の余地 | 有料。**未検証** |
| 登記所備付地図（法務省・G空間情報センター） | 公図・筆界。`legal-crosscheck` / `parking-map`。公的データなので規約制約なし | **未確認**（API形式かDLか） |

**期待しないほうがよいもの**: 登記情報（謄本）のAPIは一般提供なし（いまの謄本PDF解析が正解）／
路線価APIなし（全国地価マップのURL合成で実装済み）／Zenn・note・カクヨムは公式APIなし。

---

## F. メインPCへの受け渡し

`./secrets-sync.sh export` 済み。置き場と手順は `TODO.md` の横断作業に書いてある。
**受け取ったら置き場ごと削除する**（消すのは受け取りを確認した人）。
