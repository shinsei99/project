# API の棚卸しと段取り（2026-08-19 サブPCで作成）

**明日やること = 「APIの取得と整理」。この1枚から再開できるようにしてある。**

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
| 3 | **日本郵便の本番申込**（組織・システム登録） | 15分 | いまはテスト用stubのみ |
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
| 5 | **`zoning_service.py` の `XKT001` → `XKT002` 修正**（下の「見つかった不具合①」） | **今すぐできる** |
| 6 | **e-Stat の実装を書く**（いまは空を返すだけ。下の不具合②） | appId が要る |
| 7 | サーバー用 Maps キーに **IP制限**を足す | 事務所のグローバルIPが要る |
| 8 | **予算アラート・日次クォータ**の設定（Gemini と同じカードなので合算請求になる） | — |
| 9 | `jyuusetsu-research` に**ストリートビューを別タブで**組み込む | 取得済み。すぐ着手可 |

---

## B. いま持っているAPI（棚卸し・値は書かない）

### B-1. 2026-08-19 に取得したもの

| API | 保管先 | 変数名 | 状態 |
|---|---|---|---|
| **Google Maps / Street View** | `.env.google-maps` | `GOOGLE_MAPS_WEB_KEY` / `GOOGLE_MAPS_SERVER_KEY` | ✅ **本番・動作確認済み** |
| **日本郵便 デジタルアドレス** | `.env.japanpost` | `JAPANPOST_HOST` / `_CLIENT_ID` / `_SECRET_KEY` | △ **テスト用stubのみ**。疎通は確認済み |

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
| 日本郵便（本番） | 未申請 | 無料 |
| e-Stat | 未登録 | 無料 |
| App Store Connect | 未作成（.p8を作るだけ） | 追加費用なし |
| Google Drive | **有効化済み**だが OAuth 同意画面が未設定 | 無料 |

---

## C. 見つかった不具合（新しいAPIを取るより先に効く）

### ① 用途地域が取れていない — `jyuusetsu-research/services/zoning_service.py:18`

`XKT001` を叩いているが、用途地域は **`XKT002`** が正しい。
`legal-crosscheck/services/admin_research_service.py:154` は正しく `XKT002` を使っている。
**キーは3アプリとも持っているのに、機能だけ死んでいる。** 修正は1行＋動作確認。

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
