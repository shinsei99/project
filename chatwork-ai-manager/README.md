# AI業務マネージャー（chatwork-ai-manager）

Chatwork を業務基盤として、AI専用アカウント「claude」が**社内のAI社員**として働くシステム。
社員が普段どおりChatworkで会話するだけで、AIが会話を理解し **TODO抽出・進捗管理・
期限/放置/漏れ検知・社内資料Q&A・定時の進捗確認** までを継続的に行う。
Claude Code 型の**エージェント**（自分で複数ツールを反復実行して調べ・操作してから答える）。

> 運用ルール・アーキテクチャ詳細は `CLAUDE.md`、計画は `TODO.md`、作業履歴は `SESSION_LOG.md` を参照。

## 必要環境
- macOS / Python **`/usr/bin/python3`**（3.9系）。venv Python は使わない（claude subprocess が SIGSEGV するため）。
- `claude` CLI（ログイン済み・MAX/Pro。Anthropic APIキー不要）。
- 依存: `streamlit pandas pymupdf openpyxl python-docx`（`pip install --user -r requirements.txt`）。
- SQLite（標準・WAL・FTS5）。

## セットアップ
1. `.streamlit/secrets.toml` を作成（`.streamlit/secrets.toml.example` 参照）:
   ```toml
   chatwork_api_token = "（claude用アカウントのAPIトークン）"
   dashboard_password = "（管理画面ログインパスワード）"
   knowledge_source_dir = "（社内資料フォルダ。例: Dropbox共有フォルダ）"
   ```
2. 依存インストール: `/usr/bin/python3 -m pip install --user -r requirements.txt`
3. DB初期化（自動・冪等）: 初回起動時に `db/migrate.py` が走る。

## 起動
- 管理画面（Streamlit・port 8540）: `bash run.sh` → http://localhost:8540
- 常時起動デーモン（監視・解析・定時処理）: `bash run_worker.sh`
- **恒久化（launchd・24時間稼働・自動復旧）**: `bash install-launchd.sh`
  - 2サービス登録: `com.shinsei.chatwork-ai-manager`(dashboard) と `-worker`(daemon)。
  - worker は **flock で単一化**（多重起動不可）。

## Chatwork 設定
- claude用アカウントで API Token を発行 → `chatwork_api_token` に設定。
- 接続確認: `/usr/bin/python3 worker.py --whoami`
- 監視ルーム設定: 管理画面「ルーム設定」で対象ルームにチェック（または `worker.py --monitor <room_id>`）。

## 使い方（社員はChatworkで普通に会話するだけ）
- 依頼「田中さんに○○を明日までにお願いします」→ AIが自動でTODO化（依頼者/担当/期限/発生元を保存）。
- 進捗「確認中です」「終わりました」→ TODOを進行中/完了に自動更新。
- 質問「@Claude ○○案件どうなってる？」「メゾンドール都島501の入居者は？」→ AIが資料/履歴/TODOを横断調査して回答。
- 定時: **18:00 終業前確認 / 翌10:00 前日未完了・期限超過確認**（AIが優先度判断して必要な相手だけ確認。2026-08-18に13:00の昼の進捗確認は廃止し1日2回に変更）。

## AIが使えるツール（Common Tool Layer）
`services/agent_tools/` に安全なラッパー関数として実装。CLI入口は `agent_tool.py <tool> '<JSON>'`（`--list`で一覧）。
kb_search / chatwork_search / chatwork_get_messages / chatwork_post_message /
task_search / task_create / task_update / task_complete / task_progress_update /
project_search / project_update / tasks_needing_attention。
QA/自動解析/定時処理が**同じTool層**を共有する。

## アプリ開発（DEVELOPMENT Agent ＋ Visual Agent）※2026-08-17 追加
LINE / Chatwork から「○○アプリを作って」と言うだけで、**設計→実装→Build→起動→ブラウザで動作確認→
修正→テスト→README→Gitコミット**までAIが自分でやる。業務機能（TODO/検索/案件）とは別系統。

```
LINE/Chatwork → 既存Agent(qa) ─┬─ 業務 → 既存Tool層（変更なし）
                               └─ 開発 → dev_task_create（受付だけ・即応答）
                                            ↓ DB: dev_tasks
                                worker のループ → dev_runner.tick()（同時1本）
                                            ↓
                              claude（全ツール＋Playwright MCP）→ Workspace で開発
                                            ↓
                              進捗・質問・完了を依頼元の入口へ通知（notify）
```

- **新しい常駐プロセスは増やしていない。** 既存 worker のループに間借りする（scheduler と同じ流儀）。
- Task ID = `TASK-YYYYMMDD-XXX`。状態は
  `RECEIVED/PLANNING/RUNNING/WAITING_USER/TESTING/FAILED/COMPLETED/CANCELLED`
  （業務TODOの「未着手/進行中/完了」とは**別体系。混同しない**）。
- **再起動耐性**: 状態は全部DB。worker が落ちても起動時に `RUNNING → RECEIVED` へ戻し、
  claude の `session_id` を使って `--resume` で続きから再開する（最初からやり直さない）。
- **INTERRUPT**: 人の判断が要るとき（本番デプロイ・課金・不可逆操作・重大な仕様判断）だけ
  `WAITING_USER` で止まり、質問が入口へ届く。返事をすると同じTaskが再開する（`dev_task_answer`）。
- **Visual Agent**: 実際のChrome（headless）を操作して表示・操作・コンソール・レスポンシブを確認する。
  定義は `~/.mcp.json` の1ファイルで、**ターミナルのClaude Codeと共通**（→ `~/VISUAL_AGENT.md`）。
- **権限**: Chatworkは `dev_allowed_account_ids`（既定は管理者のみ）。社員が勝手にコードを書かせられない。
  LINEは既存の userId 許可制をそのまま使う。
- 管理画面の「🛠 開発タスク」で一覧・実行ログ・質問への回答・タスク直接投入ができる。
- 関連設定（システム設定）: `dev_agent_enabled` / `dev_model` / `dev_timeout_sec` /
  `dev_workspace`（既定 `/Users/apple`）/ `dev_mcp_config` / `dev_allowed_account_ids` / `dev_max_attempts`。

## GIS / 地図（管理物件の位置情報）※2026-08-17 追加
「この物件の近くに自社物件ある？」「管理物件を地図にして」「どのエリアに集中してる？」に答える。
**常駐AgentもターミナルのClaude Codeも同じ `services/agent_tools/gis_tools.py` を使う**（2系統に分けない）。

### データの作り方（最初に1回・台帳を更新したら再実行）
```bash
python3 ingest_properties.py          # 台帳Excel取込 → 住所→座標（未取得ぶんだけ）
python3 ingest_properties.py --stats  # 登録状況
```
- 元データは Dropbox の `★要更新★管理物件台帳.xlsx`。**ターミナルから実行する**
  （CloudStorage は launchd 常時起動からは読めない。`/bin/bash` にFDAがあれば常駐でも可）。
- 実績: **108件登録 / 88件に座標**。残り20件は**台帳の住所欄が空**（ほぼ仲介ビル）。
  台帳に住所を入れて再実行すれば地図に載る。
- **オーナーの連絡先・電話番号の列は意図的に取り込んでいない**（地図やLINEに出す情報ではないため）。

### Geocoding（住所→緯度経度）
- **国土地理院 住所検索API**（`msearch.gsi.go.jp`）。**APIキー不要・無料・政府提供**。
- OpenStreetMap の Nominatim は**利用規約で一括ジオコーディングを禁止**しているため使わない。
- 結果は `geocode_cache` テーブルに保存し、**同じ住所を二度外部へ問い合わせない**。呼び出し間隔1秒。
- ⚠️ **国土地理院は町名が特定できないと黙って区の中心座標を返す。** `geocode()` の戻りの
  `coarse=True` がその印。町名ごとに点を並べる用途では捨てること（全部同じ点に重なる）。

### ライブラリを追加していない理由（再検討しないための記録）
このMacは51本のアプリが共通の `/usr/bin/python3`(3.9) を使い、本番workerもそこで動いている。
geopandas は fiona/GDAL のバイナリを引き込むため、共有環境を壊す危険が利益に見合わない。
→ 距離は Haversine（純Python）、地図は Leaflet を読むHTMLを自前生成、GeoJSONは標準json。
**ポリゴン解析（用途地域・土砂災害警戒区域）も、shapely を足さずに実現できた**（2026-08-18）。
理由は下の「公的データ連携」参照。将来もっと大きなポリゴン集合を自前で扱う必要が出たら、
その時に隔離venvで shapely を検討する。

### Tool 一覧
`gis_property_search`（物件検索）/ `gis_nearby_properties`（半径検索・距離つき）/
`gis_distance`（2地点間）/ `gis_area_stats`（エリア別集計）/ `gis_create_map`（地図HTML生成。
`hazard_layers` でハザードマップポータルのタイルを重ねられる）/
`gis_market_map`（**既存の reinfolib_transactions を再利用**して取引価格を重ねた地図）/
`gis_land_info`（**用途地域・土砂災害警戒区域・近傍の地価公示**。国土数値情報／不動産情報ライブラリ経由）/
`gis_geocode` / `gis_export_geojson` / `gis_status`。

### 公的データ連携（TASK-20260818-004・2026-08-18 調査・1)(2)実装／3)(4)は方針のみ）

「地理空間オープンデータ公開サイトリスト.xlsx」で紹介されていた4系統を調査した結果。

**1) 国土数値情報（用途地域・地価公示・土砂災害警戒区域）→ 実装済み**
国土数値情報そのもの（nlftp.mlit.go.jp）は都道府県一括のシェープファイル配布のみで、
住所単位の問い合わせに向かない。だが**既存の reinfolib_api_key（不動産情報ライブラリ）が
同じデータをスリッピーマップのベクトルタイルAPIとして公開している**ので、
取引価格(XIT001)と同じ「1点ずつ問い合わせる」設計にそのまま乗せた（キーの新規取得は不要）。
- 用途地域 = `XKT002`（ベクトルタイル・GeoJSON。フィールドは `use_area_ja` /
  `u_building_coverage_ratio_ja`＝建蔽率 / `u_floor_area_ratio_ja`＝容積率）
- 土砂災害警戒区域 = `XKT029`（国土数値情報 A33。`A33_001`＝現象種別 1急傾斜地崩壊/2土石流/3地すべり、
  `A33_002`＝区域区分 1警戒(イエロー)/2特別警戒(レッド)）
- 地価公示 = `XPT002`（ポリゴンではなく点データ。`year` パラメータ必須・省略時は前年）
- ポリゴン内外判定は **pure-Python のレイキャスティング**（`jyuusetsu-research/services/zoning_service.py`
  と同じ手法。shapely 不要）。実装は `services/gis.py` の `zoning_info` / `sediment_hazard_info` /
  `land_price_nearby`、Tool は `gis_land_info`。
- ⚠️ `jyuusetsu-research/services/zoning_service.py` は用途地域を **XKT001**（都市計画区域/区域区分。
  用途地域ではない）で誤って叩く既知バグがある（[[reference-reinfolib-api]] 参照・本アプリとは無関係だが
  同じ穴に落ちないための記録）。

**2) ハザードマップポータルサイト（洪水・土砂災害・高潮）→ タイル重ね表示のみ実装済み**
配信データは**ラスタタイル**（地理院タイル仕様のXYZ・PNG）で、Leafletに`L.tileLayer`を
足すだけで重ね表示できる（`gis_create_map` の `hazard_layers=["flood","landslide","hightide"]`）。
**物件ごとの自動テキスト判定（重説向け）はまだ無い**。ラスタの色から危険度を判定するには
凡例の色対応表が要り、今回は着手していない。土砂災害だけは上の(1)のベクトル判定
（`gis_land_info`）で自動判定できている。洪水・高潮の自動判定は次フェーズの課題。

**3) 登記所備付地図データ → 方針のみ（未実装）**
法務省が2023年1月にXML形式で無償公開したが、**住所単位のクエリAPIではなく
都道府県・市区町村ごとの一括ダウンロード配布**（G空間情報センター経由）。組み込むには
①対象エリア（都島区・城東区など管理物件が多い区）のデータを取得
②地番ポリゴンをGeoJSONへ変換・自前ホスティング
③`gis_create_map`にレイヤ追加、という**バッチ処理基盤**が要る。まずは物件ごとに外部の
公図ビューア（例: kouzuviewer.com、法務局「登記情報提供サービス」）へのリンクを返す
簡易対応から始めるのが早い。本格導入は別タスクで着手。

**4) RESAS（地域経済分析システム）→ 使用不可・代替検討が必要**
**RESAS APIは2025年3月24日に提供終了済み**（アカウント自動削除・後継APIなし、と内閣官房
公式アナウンス済み）。代替候補は e-Stat API（政府統計の総合窓口・無料・要アプリケーションID登録）
または国土交通省データプラットフォーム(DPF)のGraphQL API。**どちらも新規のAPIキー登録が要る**ため、
勝手に登録せず人の判断を仰ぐ（[[project-chatwork-ai-manager-gis]] にも追記予定）。

### 地図の置き場所・見方
- `chatwork-ai-manager/maps/` に HTML を保存（**gitignore**。実在の所在地とオーナー名を含むため）。
- 管理画面の「🗺 物件マップ」で表示・作成・物件一覧の確認ができる。
- 背景地図は地理院タイル。LINEには画像を送れないので、**要点を文章で返し**ファイル名を添える運用。

## 業務日報の自動作成（Stage 10・2026-08-21 追加）

その日の Chatwork の会話と TODO の動きから、**社員1人ずつの業務日報**を AI が書く。
管理画面「📝 業務日報」で日付と対象者を選んで作る。運用開始はオーナー指示で**2026-08-25の週から**。

| ファイル | 役割 |
|---|---|
| `services/daily_report.py` | 会話・TODOの収集 → プロンプト組み立て → Claude → `daily_reports` へ保存 |
| `views/daily_report.py` | 管理画面。日付/対象者の選択・生成・表示・Markdown書き出し・outboxへ積む |
| `daily_reports` テーブル | `UNIQUE(report_date, person)`。作り直しても増えない（上書き） |

### 設計上わざとそうしている点（変更するときは理由を読んでから）

- **本人判定は `account_id` だけで行う。名前では判定しない。**
  2026-08-21 の実データに社員の「森」さんと入居者の「森様」が同じ会話に居た。
  名前で拾うと他人の用件が本人の実績になる。会話はルーム全体を時系列で渡し、
  本人の発言にだけ `★` を付けてモデルに示している。
- **件数はコードが数える。** モデルには数えさせない（`stats` は Python 側で算出）。
  根拠にした message_id は `evidence` に必ず残す。
- **発言0件の人は「記録なし」と書かせる。** 会話に無い業務を創作させない。
  推測は「（推測）」と明記させる。
- **Chatwork へは自動投稿しない。** `outbox.NEVER_AUTO_KINDS = {"daily_report"}` を追加した。
  `post_mode` が `auto` でも日報だけは送られず、必ず「📤 投稿承認（outbox）」で人が承認する。
  個人の日報は誤りがそのまま本人・上長の目に触れるため、ここは構造で止める。

### 使い方

1. 「📝 業務日報」→ 対象日を選ぶ（既定は本日）。
2. 会話がDBに無ければ「🔄 Chatworkから最新を取得」。**読むだけで投稿はしない**。
   ただし Chatwork API は過去に遡れず**各ルーム最新100件まで**。それより前は DB に有る分で書く。
3. 対象者（既定: 塚本・松本・森）を選び「🧠 選んだ人の日報を作成」。1人あたり30〜60秒。
4. 表示を確認 → 「📄 Word」「📊 Excel」「⬇ Markdown」で書き出す／
   必要なら「📤 Chatworkへ（承認待ちに積む）」。

### 書き出し（Word / Excel / Markdown）

`services/daily_report_export.py` が本文Markdown（`## 見出し` ＋ `- 箇条書き`）を解釈して変換する。

| 形式 | 中身 |
|---|---|
| **Word (.docx)** | 1人1ページ。「業務日報」の題字＋日付/氏名/要約の枠＋`■ 見出し`＋箇条書き。そのまま印刷・回覧できる |
| **Excel (.xlsx)** | **1シートに全員分**を縦に並べる。A列=項目 / B列=内容。並び順は画面の「対象者」で選んだ順 |
| **Markdown (.md)** | 氏名が `##`、日報の見出しが `###`。1ファイルに全員分 |

### 日報の項目（2026-08-21 オーナー指示で確定）

**次の3つだけ。増やさない。**

1. 本日の対応
2. 完了したこと
3. 進行中・明日以降に持ち越すこと

「本日の対応」は**時刻を書かず、やり取りの経過ではなく「何の件を扱ったか」を1行の要点**にする。
同じ案件の複数のやり取りは1行にまとめ、物件名・部屋番号・相手の名前・業者名は必ず残す。

- 悪い例: 「14:34 大鹿さんより西ビル3階テナント（美容室・ディークルーズ井口様）の翌日夜間の
  ビル出入りに関する問合せ対応を依頼され『承知しました』と返信」
- 良い例: 「西ビル3階テナント（美容室・ディークルーズ井口様）の翌日夜間のビル出入りに関する
  問合せを対応」

以前あった「対応した案件・物件」「依頼したこと・待っていること」「気づき・注意点（AI所見）」は
**オーナー判断で廃止した**（2026-08-21）。プロンプトの見出しリストを変えるときは
`services/daily_report.py` の `_PROMPT` を直す。表示・書き出しは見出しを固定していないので追随する。

Chatwork 投稿用は `chatwork_body()` が別に整形する。**Chatwork は見出し記法が無い**ので
`## 本日の対応` を `【本日の対応】` に、`- ` を `・` に置き換える。
`chatwork_body()` には AI所見を落とす `include_opinion` 引数が残っているが、
所見の見出し自体を廃止したので現状は効かない（所見を復活させるときのために残している）。

作るときにはまった点（次に触る人へ）:

- **`Table Grid` スタイル頼みだと罫線が出ないビューアがある。** `_table_borders()` で
  `w:tblBorders` を直接書いている。表の幅も `autofit = False` にしないと人によって変わる。
- **`add_page_break()` は空段落を1つ足す**ので、直前が箇条書きだと `□` が残って見えた。
  見出し段落の `page_break_before` で改ページする形にした。
- **Excel の行の高さは明示している。** Excel 本体は折り返しを自動調整するが、
  QuickLook など他のビューアでは潰れる。B列の幅74（≒全角37文字）から行数を見積もっている。
- **フォントは `游ゴシック`**（Office標準）。macOS の QuickLook では明朝に化けるが、
  Word/Excel で開けば正しく出る。日本語は `w:eastAsia` を指定しないと効かない。

### 実測（2026-08-21・サブPCで検証）

- 8/21（会話8件）と 8/20（会話55件）で 塚本・松本・森 の日報を生成。1本あたり約30〜60秒（sonnet）。
- 8/20 の松本さん（発言22件）は時系列12行の日報になり、内容は会話と一致していた。
- 8/21 の松本さん・森さんは発言0件。**創作せず「Chatwork上の記録なし」と書いた**。
  森さんの日報には「入居者の森様と社員の森さんは別人」という注意まで出た。
- **TODO欄が薄いのはサブPCのDBに tasks が3件しか無いため**（本番のTODOはメインPCのDBにある）。
  メインPCで動かせば「本日動いたTODO」「未完了TODO」も日報に反映される。

## 投稿モード（安全設計）
`confirm`（既定・AIの自発投稿はすべて管理画面で承認）/ `semi`（進捗確認等は自動）/ `auto`（全自動）。
管理画面「システム設定」で切替。@Claudeへの直接返信は常に送信。

## ナレッジ（社内資料RAG）
- 取込: `python3 ingest_knowledge.py [--dir <folder>] [--dry-run] [--full]`（PDF/Excel/Word/HTML/CSV/txt/.url）。
- OCR（スキャンPDF）: `python3 ocr_ingest.py`（claude vision・長時間）。
- 日次増分リフレッシュ: 既定 07:00 に worker が更新分のみ再取込（`scheduled_runs`で1日1回）。
- **⚠️ CloudStorage(Dropbox)取込はTCC権限が必要**。launchd常時起動で取込するには `/bin/bash` にフルディスクアクセスを付与。
  未付与ならターミナルから取込（検索・Q&AはローカルDBのみで常時起動でも動く）。

## バックグラウンド処理・定期処理
- worker.py が常時ループ: 新着取得→質問応答→TODO解析→定時処理→（post_modeに従い）投稿。
- ポーリング間隔・定時時刻は管理画面「システム設定」で変更可。

## 再起動・冪等
- 全状態はDB永続（TODO/進捗/確認履歴/処理済みメッセージ/定時履歴）。プロセスメモリに業務状態を持たない。
- 二重防止: messages.processed / last_message_id / outbox.dedup_key / tasks.dedup_key / scheduled_runs(UNIQUE)。
- 再起動時: 中断メッセージを pending へ戻す。同一TODO重複作成・定時ジョブ二重実行なし。


## AIがChatworkへファイルを添付送信する（Stage 9・2026-08-19）

「資料を送って」に対して**パスを案内するのではなく実際に添付する**。
2026-08-19、塚本さんが3回「図面を送って」と依頼したがAIは3回とも
「ファイル添付の送信機能は持っていません」と答えていた、という実例を受けて追加した。

| Tool | 用途 |
|---|---|
| `find_files` | 名前の一部で共有フォルダから実体を探す（**まずこれ**） |
| `chatwork_can_send_file` | 送れるかだけ先に確認する（送らない） |
| `chatwork_send_file` | 実際に添付送信する |

- 送信元は**共有フォルダ配下に限定**（`knowledge_source_dir`）。realpath で解決してから
  判定するので `..` やシンボリックリンクで外へ出られない。実測で `/etc/passwd` /
  `secrets.toml` / 共有フォルダ外の実在ファイルを `..` 経由で指したもの、すべて拒否を確認
- **5MB上限**（Chatwork側の制限）。超えるものは送らず理由を返す
- 送信は `sent_files` テーブルに**全件記録**する（blocked・failed も残る）。
  **LINE通知は既定で送らない**（2026-08-19 オーナー判断。送るたびに通知が来て煩いため撤回）。
  監視したくなったら設定 `file_send_notify_line=1` で戻せる
- 本文に**保管場所（共有フォルダからの相対パス）を必ず添える**ので、受け取った人が
  元フォルダを辿れる

### はまりどころ（実測で判明。次の担当が繰り返さないため）

1. **ファイル名がURLエンコードされて相手に見える。**
   multipart の `filename=` を RFC2231 でパーセントエンコードし `filename*=UTF-8''…` も
   併記したところ、Chatwork は `filename=` の値を**そのまま採用**し、受信側に
   `%E3%82%B0…jpg` と表示された。→ **生の UTF-8 を `filename=` に入れるのが正解**。
2. **macOS のファイル名は NFD（分解形）。**
   `os.walk`/`os.listdir` が返す `グランビルド` は「ク」+濁点で、コード中の NFC 文字列と
   `==` も `in` も一致しない。見た目が同じなので気づきにくい。
   → 比較の前に必ず `unicodedata.normalize("NFC", …)` で揃える。
     **開くときは OS が返した実体のパスを使う**（正規化した文字列で開かない）。
   これを踏むと「ファイルが見つかりません」になり、さらに `"アーカイブ" in path` も
   一致せず**アーカイブを現行と誤判定**する（両方とも実際に起きた）。
3. **同じ資料が現行とアーカイブの両方にある。**
   `グランビルド岩城3F.jpg` は `営業・募集/間取図面(新）/…` と
   `_アーカイブ（2027年7月削除予定）/…` に**同一ハッシュ**で存在した。
   アーカイブを送ると「そこを見ればある」と案内したことになり、後で参照先が消える。
   → `find_files`/`resolve` は**現行を優先**し、アーカイブしか無いときは本文に警告を付ける。
4. **送信直後の `get_file` は404を返すことがある**（Chatwork側の反映待ち）。
   数秒待って再試行すれば取れる。送信自体は成功しているので失敗と誤判定しないこと。

## LINEに送っても回答が返らない — まず送信可能メッセージ数を疑う（2026-08-20の障害）

**症状**: LINEで質問すると「受け付けました。調べています…🔎」までは来るのに、
そのあとの回答が永久に来ない。Chatworkは普通に動いている。

**原因**: LINE公式アカウントの **送信可能メッセージ数（月の上限）を使い切っている**。

LINEで課金対象なのは **push（こちらから任意のタイミングで送る）だけ**で、
**reply（reply_tokenを使った受信直後の返信）は無料・無制限**。本アプリは
「ackはreply・回答はpush」で作ってあるため、枠が切れると**受付だけ届いて回答が消える**
という、いちばん分かりにくい壊れ方をする。

**確認コマンド**（アプリrootで実行。読み取りのみ・副作用なし）:

```bash
/usr/bin/python3 -c "import sys;sys.path.insert(0,'.');from services import line_client;print(line_client.quota())"
# → {'limit': 200, 'used': 200, 'remaining': 0, 'type': 'limited'} なら枠切れ
```

枠が切れていると push は HTTP 429 と
`{"message":"You have reached your monthly limit."}` を返す。

**プランと通数**（[LY Corporation公式](https://www.lycbiz.com/jp/service/line-official-account/plan/)）:

| プラン | 月額(税別) | 無料通数 | 追加課金 |
|---|---|---|---|
| コミュニケーション | ¥0 | 200通 | **不可** |
| ライト | ¥5,000 | 5,000通 | **不可** |
| スタンダード | ¥15,000 | 30,000通 | 可（〜¥3/通） |

**月中のアップグレードは差額精算で当月から適用され、差分の通数がその場で付与される**
（ダウングレードのみ翌月適用）。つまり**月初のリセットを待たずに復旧できる**。
ライト以下は追加課金ができないので、**上限に達したらその月はもう送れない**。

**実測ペース**（2026-08-20 に LINE Insight API で測定）: 稼働日 **1日あたり約50通**、
月あたり約1,000通。無料の200通は **4日で枯渇**した。使用量は次で測れる:

```bash
curl -s -H "Authorization: Bearer $TOKEN" \
  "https://api.line.me/v2/bot/insight/message/delivery?date=20260819"
# apiPush が課金対象、apiReply は無料
```

**送信数はメッセージオブジェクト単位で数える。** `line_client._text_messages()` は
長文を4800文字ごとに分割するので、**長い回答は1回のpushで複数通を消費する**。

### プランを上げるときの詰まりどころ（2026-08-20に実際に踏んだ）

**Safari では支払い方法の登録画面が出ない。Chrome を使う。**

Safari で `manager.line.biz` を開くと、プラン購入の確認画面（¥5,000＋税＝¥5,500・
差額請求）まで進めるものの、利用規約にチェックを入れても **「購入」ボタンがグレーのまま**で
押せず、カード入力画面にも到達しない。「エラーが発生しました。もう一度お試しください」と
いう理由の分からない汎用エラーだけが出る。

**同じ操作を Chrome で行うと、カード入力画面が正常に表示された。**
Safari は `access.line.me` のLINEアカウント認証へ飛ばず、メールアドレスの
ビジネスアカウントのセッションのままだったため、支払い方法の登録に進めなかったとみられる
（Safariのサイト超えトラッキング防止の影響も疑ったが、**どちらが決め手かは未確認**）。

手順の順番にも注意する。**購入画面にはカード入力欄が無い。**
先に **設定（歯車）→ 利用と請求 → お支払い方法** でカードを登録し、そのあと
**月額プラン → アップグレード → 購入** の順で進める。支払い方法が未登録だと
「購入」ボタンは有効にならない。

### 実装されている再発防止（2026-08-20）

- `line_client._post()` は失敗理由を捨てない。429を「枠切れ」と判別し `last_error()` で読める
- 枠切れは `settings` の `line_quota_exhausted` に記録される
- `worker._watch_line_quota()` が**1日1回**残通数を見て、残り1割以下で予告・0で枠切れ通知
- 通知先は **Chatwork**（`services/line_alert.py`）。以前は障害通知もLINEのpushで送っていたため、
  「LINEの枠切れ」という障害では**通知自体が同じ理由で届かなかった**。この循環を断ってある
- push の呼び出し元は `label=` としてログに出る（`[line] push ok label=qa_answer messages=2`）。
  どの経路が枠を食っているかはこのログで数える

### 遠隔からの切り分け（サブPCなど社内LANの外から）

**サブPCから 192.168.1.105 にpingが通らないのは異常ではない**（サブPCは別ネットワークに居る）。
外側から確かめられるのは次の3つで、これがメインPCの生死を知る唯一の手段になる。

```bash
curl -s https://<ngrok固定ドメイン>/          # → line-webhook ok なら line_webhook は生存
curl -s -X POST https://api.line.me/v2/bot/channel/webhook/test \
  -H "Authorization: Bearer $LINE_TOKEN" -H "Content-Type: application/json" -d '{}'
                                              # → success:true なら LINE→メインPC の到達もOK
curl -s -H "X-ChatWorkToken: $CW_TOKEN" https://api.chatwork.com/v2/me
                                              # → 200 なら Chatworkトークン有効
```

Chatwork worker が生きているかは、監視ルームの直近メッセージに claude の返信があるかで見る
（`GET /rooms/<id>/messages?force=1`）。**`unread_num` / `mention_num` は判断材料にならない** —
workerは既読を付けず `last_message_id` で境界を管理するので、これらは正常でも増え続ける。

## トラブルシューティング
- worker が応答しない: `ps -eo pid,command | awk '/MacOS\/Python worker\.py$/{print $1}'` で稼働確認（1個であるべき）。
  再起動は `launchctl unload/load ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager-worker.plist`。
- claude が落ちる(-11): venv Python を使っていないか確認。必ず `/usr/bin/python3`。
- 日本語検索が弱い: FTSは trigram、索引は NFKC 正規化済み（半角/全角カナ吸収）。
- ログ: `~/Library/Logs/com.shinsei.chatwork-ai-manager*.log`。

### 「処理中にエラーが発生しました: ClaudeError」が返る＝まずトークン更新を疑う（2026-08-19 実証）

**症状**: LINE/Chatworkの返答が全滅し、13分待たされて `ClaudeError` だけが返る。
worker の解析(extract)も同時にタイムアウトする。**worker を再起動しても直らない。**

**正体**: claude CLI の **OAuthトークン更新がハング**すると、APIを叩く前段で止まる。
トークンは全プロセス共通のKeychainにあるため、**worker も line_webhook も同時に沈む**。
アプリのバグではないので、コードを見ても何も見つからない。

**3分で切り分ける手順**（この順に叩く）:

```bash
# ① 復旧しているか（一番速い判定。平常は5〜10秒で返る）
time /opt/homebrew/bin/claude -p "1+1は？数字だけ答えて" --model sonnet

# ② トークンが最後に更新された時刻（UTC）。障害の終了時刻と一致するはず
security find-generic-password -s "Claude Code-credentials" | grep mdat

# ③ 完走した claude が居るか。障害中は「1件も無い」のが特徴
ls -lt ~/.claude/projects/-Users-apple-chatwork-ai-manager/*.jsonl | head
#    ※セッション記録は完走時に一括で書かれる。ハングした実行は痕跡を残さない

# ④ 実際に何秒でタイムアウトしたか
sqlite3 data/app.db "SELECT id,kind,error,created_at FROM ai_analysis_logs \
  WHERE error LIKE '%秒を超えました%' ORDER BY id DESC LIMIT 20;"
```

**見分け方（ここを間違えない）**:

| 観測 | 意味 |
|---|---|
| 親の計測は長いが、セッション記録内の実作業は数十秒 | **トークン更新待ち**。APIは遅くない |
| Chatworkのメッセージ取得(`messages.fetched_at`)は成功し続けている | ネットワークは正常。Anthropic宛だけの問題 |
| worker再起動で直らない／再起動していない line_webhook も一緒に復旧する | プロセス状態ではなく**共有状態**（Keychain）が原因 |
| `status.claude.com/api/v2/incidents.json` に該当なし | **公表されない詰まりがある。**statusページを復旧判断に使わない |

**対処**: 待てば直る（2026-08-19の実績で約50分）。**コードは触らない。**
復旧後、障害中の依頼は**黙って消えている**（`dev_tasks` に入らない）ので、取りこぼしを確認して再依頼する。

## 主要ファイル
`worker.py`（デーモン）/ `app.py`＋`views/`（管理画面）/ `services/`（sync, analyzer, qa, scheduler,
chatwork, tasks, projects, knowledge, outbox, settings, agent_tools/,
**dev_tasks, dev_runner, notify**）/ `agent_tool.py`（Tool CLI）/
`db/`（schema, migrate, connection）/ `kb_search.py` / `ingest_knowledge.py` / `ocr_ingest.py` / `install-launchd.sh`。

## 運用メモ（ルート CLAUDE.md から移動・2026-08-17）

> 元の見出し: 「AI業務マネージャー（chatwork-ai-manager）補足 ※不動産・画面8540／LINE8530」
> **他PCと共有される情報。** ここを直せば2台で同じ内容になる。

- 詳細は `chatwork-ai-manager/README.md`（gitに入っている）と、同フォルダの `CLAUDE.md` / `TODO.md` /
  `SESSION_LOG.md`（識別子を含むため**gitignore**。Dropbox-個人のtarで運ぶ）。
- **⚠️ worker / LINE webhook / ngrok は「同時に1台のPCだけ」。** 2台で動かすとChatwork・LINEへ
  二重返信し、ngrok固定ドメインを奪い合う。移すときは先に旧PCで
  `launchctl unload ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager*.plist`。
- **PCをまたぐ引き継ぎ**: コードはgit、機密（secrets・`data/app.db`・内部docs・ngrok token）は
  `handoff_export.sh` → Dropbox-個人 → `handoff_import.sh`。**DBは双方向マージできない**ので、
  常駐を移す直前に必ず export→import で最新へ揃える。
- Python は **`/usr/bin/python3` 固定**（venv Python だと `claude` サブプロセスが SIGSEGV）。
