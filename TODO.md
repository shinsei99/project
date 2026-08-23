> ## 🖥 メインPCでやること — 引き継ぎまとめ（2026-08-23 サブPCより／8/19以降の3日ぶん）
>
> **メインPCの最終作業は 2026-08-19。以降サブPCで 8/20・8/21・8/22 の3日ぶんが進み、すべて push 済み**
> （HEAD `314782e` 2026-08-22。サブPC側は未コミット・未pushとも 0 件を `./dev-doctor.py --sync --fetch` で確認）。
>
> **上から順にやる。A だけで本番は正しくなる（30〜40分）。**
> 各項目の詳細は下の日別ブロックと各アプリの README にある。
>
> ---
>
> ### A. 本番に効かせる（最優先・これをしないと直したものが1つも動いていない）
>
> **A-0. コードを取る**
>
> ```bash
> cd ~ && git pull
> ```
>
> **A-1. APIの資格情報を受け取る（先にやる。これが無いと新しいToolが動かない）**
>
> 8/19以降に取ったキーがメインPCに1件も渡っていない。**個人Dropboxに置いてある**:
>
> ```
> Dropbox-個人/apps-secrets-handoff/apps-secrets-MacBookAir.tar （992K・33項目・2026-08-21 21:18・存在確認済み）
> ```
>
> ```bash
> cd ~ && ./secrets-sync.sh check     # 何が無いかを見る
> ./secrets-sync.sh import            # 取り込む（既にある物は上書きしない）
> ./secrets-sync.sh check             # 「不足 0 件」を確認
> ```
>
> 新しく渡るもの: `.env.google-maps`（Web/Server/**Embed** の3キー）／`.env.japanpost`（本番）／
> `.env.estat`（**8/23からAI業務マネージャーの商圏統計Toolでも使う**）／`.env.appstore` ＋ `.appstore/AuthKey_*.p8`（**再発行不可**）／`mail-archiver/.env.mail-archiver`。
> ほかに既存19件も入っているが上書きされない。
>
> **★不足0件を確認したら `apps-secrets-handoff/` を置き場ごと消す**（機密を同期フォルダに残さない決まり）。
>
> **A-2. 人の手が要る設定を2つ入れる（コードでは解決しない。A-3の再起動より前に）**
>
> 1. **日報メールのSMTP**（`chatwork-ai-manager` の機密は `secrets-sync` では運ばれない）
>    ```bash
>    security add-generic-password -s chatwork-ai-manager-smtp -a shin@daikyocorp.co.jp -w
>    ```
>    ＋ `chatwork-ai-manager/.streamlit/secrets.toml` に5行（`secrets.toml.example` からコピー）。
>    ホスト・ポート・暗号化は実測確定済み（`smtp.daikyocorp.co.jp` / **587のみ** / STARTTLS / 上限30MB）。
>    **サブPCで認証・実送信まで確認済み**（2026-08-21・自分宛）。入れるまでは送らず「設定が足りない」を
>    日報の結果に記録して管理者へ通知する（黙って止まらない）。
> 2. **`/bin/bash` にフルディスクアクセス**（システム設定＞プライバシーとセキュリティ）。
>    launchd 常駐は CloudStorage を読み書きできない。無いと**業務日報の保管も休業日判定も失敗する**:
>    保管先 Dropbox『社内・総務/業務日報』／休暇表 GoogleDrive『ルーティーン/年間休暇スケジュール2026.xlsx』。
>    （`shorui-cabinet` 8528 で同じ対処を実施済み [[reference_launchd_cloudstorage_fda]]）
>
> **A-3. 常駐を入れ替える**
>
> ```bash
> launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-worker
> launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-line
> launchctl kickstart -k gui/$(id -u)/com.shinsei.maisoku-converter
> lsof -nP -iTCP:8505 -sTCP:LISTEN   # *:8505 で待ち受けていること
> ```
>
> `services/line_client.py` は worker と line_webhook の**両方**が読むので、片方だけでは不足。
> ngrok（`-ngrok`）は触らなくてよい。
>
> **worker は 8/19 09:00 起動のまま＝3日ぶんの修正が1つも本番に入っていない。** 溜まっているもの:
>
> 1. TASK-20260819-002（QAが未実行のTODO更新を「反映しました」と嘘をつく不具合）
> 2. TASK-20260819-003（QAのTODO一覧回答を定時確認と同じ担当者グループ化に統一）
> 3. **LINE無反応の再発防止**（失敗の握りつぶし修正・Chatworkへフォールバック通知・残通数の日次見張り）
> 4. **業務日報**（毎日18:30の自動処理。**サブPCに worker は常駐していないのでメインPCでしか動かない**）
> 5. **AIのToolを4系統追加**（法令の現行条文＝e-Gov／郵便番号と住所の照合＝日本郵便／
>    ストリートビューのリンク＝Google Maps／**商圏の政府統計＝e-Stat**（8/23追加。人口・世帯・
>    高齢化率・転入超過・将来推計／空き家率・借家率・共同住宅率・着工新設貸家。区どうしの比較も可））。
>    法令はキー不要、**郵便番号・ストリートビュー・商圏統計は A-1 が前提**（`.env.estat` も要る）。
>    ストリートビューは**リンクを返すだけ**（SV画像をAIに読ませない・印刷しないの線引きは README に記載）。
>    `{"property":"○○"}` の形は物件マスタDBがサブPCに無く試せていない → **メインPCで一度確認すること**
> 6. **休業日は定時確認を送らない**（8/22 の `314782e`。年間休暇スケジュール上の休業日 8/22（土）に
>    18:00の定時確認が飛んだ件。休業日判定が業務日報にしか入っていなかった）。
>    **★8/23（日）も休業日。再起動するまで日曜・休業日にも催促が飛び続ける**
>
> マイソクコンバーター(8505)は**社内LAN共有あり**＝入れ替えないと、貼った画像が横1.2倍に伸びる
> 修正前のコードが社員に出続ける。
>
> 手順・確認コマンド・本番に入る中身の一覧は `chatwork-ai-manager/README.md` 先頭
> 「★ メインPCで最初にやること」に一本化してある（SESSION_LOG/TODO は gitignore で届かないため）。
>
> ---
>
> ### B. 人にしかできない外部手続き
>
> - **LINE のライトプラン（月5,000通・¥5,000税別）への変更。** 無料枠200通は4日で枯れる
>   （実測 1日約50通）。**未実施なら枠は0のまま＝LINEは無反応のまま。Safari では支払い画面に
>   進めない**ので別ブラウザで（README に記録済み）
> - 法人番号Web-API は申請完了済み（**発行見込み 2026-09-04〜09-21**）。届いたら `API_STATUS.md` を更新
>
> ### C. メインPC限定の作業（配布証明書・実機・常駐がこちらにしかない）
>
> - ~~**App Store の審査結果を3本確認**~~ → **2026-08-23 にサブPCから API で確認済み**
>   （`python3 appstore_api.py --review` を追加した。**メインPCでなくても分かる**）。
>   結果: **スクラップメモ 1.0.4/build8 は配信中**（CLAUDE.md を更新済み）／
>   **デジタル書斎 1.0 と KeyTag 1.0 はまだ審査待ち**（提出から4〜6日・審査に入っていない）／
>   **にゃんこのアイス屋さんは「申請中」ではなく未提出**（1.0が提出準備中・ビルド0件。CLAUDE.md を訂正）。
>   デジタル書斎・KeyTag は結果が出るまで待ち。もう一度見るときは上のコマンドを叩く
> - **デジタル書斎を実機で1度通す**（手順 `digital-shosai/HANDOFF-APPSTORE.md`）
> - **KeyTag は NFCタグ到着後に実機検証**（NFC機能は一度も実機で動かしていない）
> - **業務日報の初日を見届ける**（**次の営業日 8/24（月）18:30**。8/23（日）は休業日で動かない）。
>   テストはサブPCで 8/21 に完了。18:30 は**承認を挟まず Excel が Chatwork へ上がる**
>   （オーナーの明示指示。止めるなら設定 `daily_report_upload=0`）。残る未確認は、サブPCのDBに
>   tasks が3件しか無く**「本日動いたTODO／未完了TODO」欄だけ実データで動かせていない**という1点
> - `mail-archiver`(8535) をメインPCで常駐させるなら A-2 の `/bin/bash` FDA が前提
>
> ### D. 余力があれば
>
> - **ポケモンカード図鑑の相場は週1回**更新するとよい（`.venv/bin/python ingest_tcgdex_price.py`）
> - ~~note `nanka-ugokanai` はメインPCから~~ → **完了済み。メインPCの出番は無い**
>   （Zenn `ai-intake-hearing` は 8/20 23:40 に反映、note は 8/21 07:53 に公開）。
>   **2026-08-23 に実データで数え直した結果、AIツールベースの3点セットは
>   本体9 / Zenn9 / note9 で揃っており、公開待ちは0本**（本体の制作記録15本のうち
>   転載対象は不動産カテゴリの9本。ツール5＋メディア1は方針どおり本体のみ）
>
> ### E. アプリの増減（`git pull` で手元の構成が変わる）
>
> **総数は 52本のまま**（メインPCが最後に触った 8/19 も 52本）。**中身が1本入れ替わった**だけ:
> ツールが1本増え（メールアーカイバ）、不動産が1本減った（legal-crosscheck を吸収）。
> 内訳は 不動産**31** / ツール**15** / ゲーム6。CLAUDE.md の一覧は更新済み。
>
> - **新規: メールアーカイバ `mail-archiver`（8535・ツール）**。IMAP容量対策で `.eml` を
>   ローカル保管＋FTS5全文検索、取込から14日たったぶんだけサーバーから削除する。
>   **launchd 未登録・`127.0.0.1` 固定**（メール本文＝個人情報なので社内LANには出さない）。
>   残作業は ①iCloudのApp用パスワード発行→IMAP取込 ②Tailscale導入（人の作業）③`restore.py`
> - **削除: `legal-crosscheck`**。`jyuusetsu-research` の④タブへ完全に吸収した。
>   **`git pull` するとメインPCからもフォルダごと消える**（launchd 登録・`.url` は元から無し）。
>   `tokuyaku-generator`（8513）は**畳んでいない。恒久的に残す**
> - **直下に共有モジュールが増えた。コピーを作らないこと**:
>   `registry_parser.py`（謄本解析）／`tokuyaku_clauses.py`・`tokuyaku_core.py`（特約170項目）／
>   `doc2docx.py`／API関係4本（`appstore_api.py` `egov_law_api.py` `google_maps_api.py`
>   `japanpost_api.py`）と `API_STATUS.md` `GOOGLE_MAPS_API.md`
> - **`jyuusetsu-research` は port 8536 を予約したが、まだ開発中で launchd 未割当**（配布もしない）
>
> ### F. この3日でサブPCが終わらせたこと（メインPC側の作業は不要）
>
> - **重説アプリの大改修**（8/21）: `legal-crosscheck` を吸収してアプリ削除。全宅連の公式書式200本を
>   取得・分類。共有モジュール3本を直下に新設＝**コピーを作らないこと**。
>   残りは「4書式を出力して Excel を目で見る」の1つ（サブPCで続ける）
> - **Intel Mac で AI解析が黙って無効になるバグを修正**（`CLAUDE_BIN` が `/opt/homebrew/bin/claude`
>   固定だった。`baikai-generator` と `tokuyaku-generator` の両方）
> - **マイソクコンバーター**: A4縦対応＋貼った画像の横1.2倍伸びを修正（Excel実測確認済み）→ A-3で反映
> - **ポケモンカード図鑑に相場**（8,346件・25.9%で表示・円換算つき）
> - **APIの棚卸しで「未確認」6件を解消**＋**法人番号Web-API を申請完了**
> - **AIツールベース 9本目を3媒体とも公開し本番反映まで完了**（8/22）:
>   Zenn `openpyxl-row-height-autofit` ／ note `moji-ga-kireteru` ／ 本体 `/works/excel-row-height`
>   （`npx vercel --prod` 済み・リンク確認済み）。**次は10本目の題材選び**
> - **休業日は定時確認を送らないようにした**（8/22）→ A-3 の再起動で本番に入る

# TODO — 全アプリの索引

> ## 🖥 2026-08-21（サブPC・午後）— 重説アプリの大改修。次はここから
>
> **`jyuusetsu-research` を「調査 → 書類作成 → 特約 → 検算」の一本道にした。** 完了条件は
> **10/11 達成**。残るのは「4書式それぞれを出力して Excel を目で見る」の1つだけ。
>
> **① 全宅連の公式書式200本を Dropbox に取得・分類**（`契約・書類/書類雛形/`）。
> `.doc` 14本も `doc2docx.py` で .docx 化（うち6本に入力表あり）。アプリに同梱していた
> **他社の実案件入りテンプレート4本は使うのをやめた**（前案件の貸主名が残ったまま出る状態だった）。
>
> **② 共有モジュールを3本作った（直下）。コピーを作らないこと。**
> - `registry_parser.py` … 謄本解析。実体は `baikai-generator` にあった完成品。8517は薄い入口
> - `tokuyaku_clauses.py` / `tokuyaku_core.py` … 特約カタログと本文生成。8513は薄い入口
>
> **③ `legal-crosscheck` を吸収してアプリを削除**（53本→52本／不動産32→31）。
>
> **④ 見つけて直したバグ（他アプリにも影響）**
> - `CLAUDE_BIN` が `/opt/homebrew/bin/claude` 固定で、**Intel Mac では AI解析が黙って無効**
>   （`baikai-generator` と `tokuyaku-generator` の両方。エラーも出ない）→ 実体を探すようにした
> - `legal-crosscheck` 由来の**偽の🟢一致**と、建ぺい率で**必ず落ちる正規表現**
> - Web法令調査の `--tools` の渡し方（300秒タイムアウト → 71秒で完了）
>
> **⑤ ストリートビューの403を解消**（Maps Embed 専用キー `maps-embed-internal` を作成）。
>
> **★次にやること**: 4書式を出力して `./see.sh file <出力.xlsx>` で目視。
> そのあとは UI の作り込み（いまサイドバーを触るたび調査からやり直しになる）。
> 詳細は `jyuusetsu-research/SESSION_LOG.md` の 2026-08-21「その2」。
>
> **★注意（解消済み）**: `maisoku-converter/app.py` の未コミット変更（別セッションの縦マイソク対応）は
> **2026-08-21 に検証のうえコミット・push 済み**（`46ce8c7`）。作業ツリーは空。

> ## 🖥 2026-08-21（サブPC）で進んだこと — 次はここから
>
> **① AI業務マネージャーのLINE無反応を解決した（原因確定・コードはpush済み）**
> 原因は **LINEプッシュの無料枠切れ**（200/200。LINE自身が `You have reached your monthly limit.`
> を返して確定）。Chatworkは最初から正常だった。**★メインPCで反映が必要**:
> ```bash
> cd ~/chatwork-ai-manager && git pull
> launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-worker
> launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-line
> ```
> `services/line_client.py` は worker と line_webhook の**両方**が読むので片方だけでは不足。
> 調べた事実は `chatwork-ai-manager/README.md` の「LINEに送っても回答が返らない」節にある
> （SESSION_LOG/TODOはgitignoreでメインPCに届かないため、READMEに書いた）。
> **LINEのプラン変更（ライトプラン月5,000通）はオーナーが実施中。** 未完了なら枠は0のまま。
>
> **② ポケモンカード図鑑に相場を追加した**（`ingest_tcgdex_price.py` 新設・`app.py` に表示）。
> 8,346件取り込み、**8,175枚（25.9%）で相場が出る**。為替連動の円換算つき。
> 相場は日々動くので**週1回 `.venv/bin/python ingest_tcgdex_price.py` を回す**とよい
> （サブPCなのでlaunchd登録はしていない）。
>
> **③ APIの棚卸しで「未確認」を6件潰した**（詳細は `API_STATUS.md` の E-2）。
> RESAS=提供終了／Pokémon TCG API=実質停止でTCGdexへ代替／登記所備付地図=API不要・DL／
> PSA公開API=承認制で403・代替ルートで解決済み（見送り）／銀行API=要情報2つ／
> Document AI=月1,000ページ無料だが精度比較は未測定。
>
> **④ 法人番号Web-APIを申請完了**（橙＝法人番号のみ。フォーム 2026-08-20 ＋ メール 2026-08-21）。
> **発行見込みは 2026-09-04〜09-21。** 橙のため**インボイスWeb-APIは含まれない**（★3は別申請のまま）。
>
> **⑤ 解決済（2026-08-22）: サブPCから note へ自動投稿できる。**
> できなかったのは `~/.mcp.json` の **Playwright（`--isolated --headless`＝ログインが残らない）**の話で、
> **Claude in Chrome 拡張（普段のChromeのセッション）なら投稿できる**（8/22 に実証・ボット検知にも掛からず）。
> ただし `computer` の `cmd+v` は**合成キーにOSのクリップボードが載らない**ので貼れない。
> `javascript_tool` で `text/html` を入れた `ClipboardEvent('paste')` を `.ProseMirror` に投げる。
> 詳細は `ai-tools-base/SESSION_LOG.md` の 2026-08-22 の節。
>
> **人にお願いする残り**: 上記①の反映／★2 Dropbox APIのアプリ作成／★3 Google Drive・
> Search Console・Analytics（Console操作）／銀行APIは**取引銀行と会計ソフト**を教えてもらえれば再開。

> ## 🖥 サブPCの作業を受領した（2026-08-18 メインPCで実施）
>
> **合流は完了。** サブPCの22コミット と メインPCの未pushだった27コミット（KeyLine/KeyTag・
> chatwork開発エージェント等）を合流させ、push済み。両PCとも `git pull` すれば同じ状態になる。
>
> | サブPCからの依頼 | 結果 |
> |---|---|
> | ① `.dev-role` を main に | ✅ 済 |
> | ② `ai-tools-lab` → `ai-tools-base` の実体移動 | ✅ 済（node_modules/.next/.vercel/.env.local を移し、空フォルダを削除） |
> | ③ `dev-doctor.py --sync --fetch` | ✅ 実行。Python 3.9.6 / Node 26.3.1 は基準どおり。常駐36本＝メインPCなので正常 |
> | ⑤ MCP設定の受け渡し | ✅ **不要になった**。`.mcp.json` は git に入っており、今回のpushでサブPCへ渡る |
> | ⑥ メモリ差分の受け取り | ✅ 済（本文2本を取込・重複1本を統合・索引を更新。Dropboxの置き場は削除済み） |
> | ④ Zenn 残り1本 → note | ✅ **Zennは 2026-08-18 夜にサブPCで実施**（下の返信ブロックを見る）。noteは未 |
> | ⑦ `--verify` の試用 | ⬜ 未（触ったアプリが出たときに使う） |
> | ⑧ デジタル書斎の App Store 提出 | ✅ **済（2026-08-19 メインPCで審査提出・1.0.0/build1）**。次は審査結果の確認と実機で1度通すこと。手順は `digital-shosai/HANDOFF-APPSTORE.md` |
>
> **メインPCからサブPCへ返すこと（次にサブPCで `git pull` したら読む）**
>
> - **共通Visual Agent を統合した**（下の横断作業を見る）。`git pull` → `./visual-agent-check.sh` だけでよい
> - **メモリの実体20本がメインPCに無い**（索引にはあるのに本文が来ていない）。次の受け渡しで
>   Dropbox に置いてほしい: `project_chatwork_ai_manager` / `project_color_gravity` /
>   `project_cyborg_defense` / `project_fudosan_novel` / `project_kaitori_dm_maker` /
>   `project_kato_kyakuzuke` / `project_mansion_kanri` / `project_memorandum_generator` /
>   `project_pasha_calo` / `project_pokecard_profit` / `project_publish_setup` /
>   `project_shared_folder_reorg` / `project_shorui_cabinet` / `project_shorui_sender` /
>   `project_soufu_maker` / `reference_dropbox_url_icons` / `reference_pdf_orient` /
>   `reference_streamlit_bind` / `reference_this_pc` / `reference_xls_images`（すべて `.md`）
> - **KeyTag（iOSアプリ）を渡す上での注意（2026-08-18に判明）**
>   - `ios/` は gitignore。サブPCでは `cd keyline/keytag && ./setup-ios.sh` で作り直す
>     （NFCのentitlement・ATS例外・署名・**版数**まで一発で当たる）
>   - **版数は `keytag/version.json` が正**にした。build番号を上げたら pbxproj と version.json の
>     両方を揃える（片方だけだと、作り直したときに build 1 に戻って古いビルドが配信される）
>   - **署名（配布証明書と秘密鍵）はメインPCのキーチェーンにしか無い → App Store提出はメインPC限定**
>   - `keyline/data/` は gitignore（社員名・鍵番号）。サブPCのサーバーは空DBから始まる
>   - サブPCに Xcode が入っているかは**未確認**。無ければビルド自体ができない
> - サブPCに残っている `stash@{0} pre-origin-sync` とローカルブランチ2本は、**中身を見てから**消す
>
> **メインPCの現状**: 常駐36本・社内LAN共有あり（＝正常）。chatwork-ai-manager の4サービス
> （画面8540 / worker / LINE 8530 / ngrok）は 2026-08-18 11:33 に再起動し、稼働を確認済み。

> ## 🖥 サブPCで実行済み（2026-08-18 夜）— メインPCへの返信
>
> 依頼①〜④は**すべて完了**。⑤KeyTag は触っていない（提出はメインPC限定のため）。
>
> | 依頼 | 結果 |
> |---|---|
> | `git pull` | ✅ 48コミットを fast-forward で取り込み |
> | ① `dev-doctor --sync --fetch` / `dev-setup.sh --all` | ✅ 対象0本。**`dev-setup.sh` の空配列バグを修正**（bash 3.2 + `set -u`） |
> | ② `visual-agent-check.sh` | ✅ 入口A（MCP）・入口B（`./va.sh`）とも全項目 ✅ |
> | ③ `secrets-sync.sh import` | ✅ **`keyline/data` を受領**（DB 180KB＋免許証画像）。機密の不足は**0件**に |
> | ④ `secrets-sync.sh export` | ✅ 18件・980K → `Dropbox-個人/apps-secrets-handoff/apps-secrets-appurunoMacBook-Air.tar` |
> | ④ メモリ実体20本 | ✅ **20/20・168K** → `Dropbox-個人/handoff-20260818-sub-to-main-2/memory/` |
>
> **★メインPCでやること: 上の2つを受け取ったら、`./secrets-sync.sh import` と
> メモリ20本のコピーを実行し、`handoff-20260818-sub-to-main-2/` を置き場ごと削除する**
> （受け取りを確認した人が消す。件数20・168K を `ls`/`du` で見てから）。
>
> **回答: サブPCに Xcode 16.1 (16B40) が入っている**（メインPCで「未確認」だった点）。
> KeyTag のビルド自体は可能。ただし配布証明書はメインPCのキーチェーンにしか無いので、
> **App Store 提出はメインPC限定**という結論は変わらない。
>
> **後始末（2026-08-18 夜・サブPCで実行済み）**
>
> - `stash@{0} pre-origin-sync` と ローカルブランチ `pre-sync-backup-20260626` を **破棄した**
>   （中身は未追跡ファイルのみ＝作業ツリーのほうが新しい／固有コミットは PR #1 で main に既出、と
>   確認したうえで実行。復元用SHA: stash `9812065` / branch `b507e7c`。reflog にも残る）
> - **メインPC発の機密 tar（`apps-secrets-usernoMac-mini.tar`）を削除した。**
>   中身13件すべてが手元に実体としてあることを1件ずつ確認してから消している
>
> **★メインPCで受領・実施した（2026-08-19）**
>
> | 依頼 | 結果 |
> |---|---|
> | 1. `./secrets-sync.sh import` | ✅ **機密5件を取り込み**（brain-dump/.env.local, pasha-calo/.env.local, ai-ticket-counter/.env, theta-viewer/server/ftp-config.json, kaitori-dm-maker/senders.json）。既存13件は上書きせず据え置き |
> | 2. メモリ実体20本 | ✅ **20/20 取り込み・540K**。索引にあって本文が無いものは**0件**になった（中身が空でないことも1本ずつ確認） |
> | 3. 確認プロンプトを減らす設定 | ✅ 控えを取って合流したが、**6件とも既にメインPCに入っていた**（追加0件・既存51件は1件も消していない） |
> | 3-b. `theta-viewer` のドキュメント | ✅ **README を実体のある内容に書き直し、SESSION_LOG.md / TODO.md を新規作成**（コミット `1c4b4d6`）。実物のコードを読んで書いた |
> | 4. 置き場の削除 | ✅ **削除済み**（2026-08-19）。`handoff-20260818-sub-to-main-2`(180K) と `apps-secrets-handoff`(988K) の2つ。**消す前に、メモリ20/20・機密5件・tar内20件すべてが手元に実体としてあることを1件ずつ確認**した |
>
> **★サブPCへ返す・要判断（2026-08-19 メインPCより）**
>
> - **`Bash(python3 *)` と `Bash(curl *)` はメインPCでは許可のまま残す**（2026-08-19 オーナー判断・決着）。
>   サブPCは「メインPCには渡さない」と判断していたが、メインPCには**既に両方入っていた**。
>   外すと確認プロンプトが増えるため、**現状維持**とした（「いまより確認は増やしたくない」）。
>   **この件は決着済み。サブPCは再提案しないこと。**
>   なお渡さない理由（python3から削除・上書き・外部送信ができ、`git`/`rm`/`launchctl` を
>   許可していなくても迂回できる）自体は有効なので、**メインPCで破壊的な操作をするときは
>   許可されているからといって自動で進めず、これまでどおり人に確認する**（運用でカバーする）。
> - `/fewer-permission-prompts` はまだ回していない（`launchctl` `lsof` `xcodebuild` `sips` などを拾う想定）

> ## 🖥 サブPCへの引き継ぎ その2（2026-08-19 夜・メインPCより）— PSAカード管理／ポケモンカード図鑑
>
> **`git pull` だけで揃う。機密ファイルの受け渡しは不要**（変更したのはコードと文書だけ）。
>
> | もの | 場所 | 備考 |
> |---|---|---|
> | ポケモンカード図鑑を PSA管理の中から開く仕組み | `psa-collection/app.py` ＋ `pokecard-dex/app.py` | 画面のコードは**図鑑側の1本を共有**（写していない） |
> | アルバムの「⭐ 欲しいカード」 | `psa-collection/app.py` | `albums.json` に `dex:<図鑑キー>` で入る |
> | launchd の登録漏れ2件を追記 | `_launchd/install-launchd.sh` | psa-collection(8527) と pokecard-dex(8531) |
>
> **サブPCで気をつけること**
>
> - **図鑑データ（`pokecard-dex/data` 4.3GB）が無いPCでは、図鑑の選択肢は出ない**。
>   PSAカード管理はそれで普通に動く（オプション扱い）。慌てて用意しなくてよい
> - **`./install-launchd.sh` をサブPCで実行しないこと**。常駐はメインPCだけの決まり
>   （サブPCの launchd 常駐は0本のまま）。図鑑を見たいときは `cd pokecard-dex && ./run.sh`
> - **PSAカード管理のデータ（`psa-collection/data`）は gitignore**。サブPCに無ければ
>   CSVが無い旨の画面が出るだけ。持ち込みは README「別PCへの引き継ぎ」のとおり
> - 図鑑の画像パスは**DBに相対で入っている**。触るときは `_p()` を必ず通す
>   （通さないと単独起動では動くのに PSA管理からは1枚も出ない、という形で壊れる）
>
> **決着した判断（再提案しないこと）**
>
> - **図鑑の実体は `pokecard-dex/` のまま**。いったん `psa-collection/dex/` へ移す方針で
>   着手したが、本人判断で撤回した（移動は元に戻してある）
> - **保有カードと図鑑カードの自動突き合わせはしない。** PSA側にはポケモン以外の
>   カードもあり、CSVは英語表記・図鑑は日本語で名前が繋がらない。連携はアルバムだけ
> - **バインダーでは保有カードと欲しいカードを混ぜない**（上下2枠・枠をまたぐ並べ替えなし）

> ## 🖥 サブPCへの引き継ぎ（2026-08-19 メインPCより）
>
> **`git pull` だけで揃う。** 機密ファイルの受け渡しは**不要**（デジタル書斎は完全オンデバイスで
> `.env` もキーも無い）。この日にメインPCで入ったもの:
>
> | もの | 場所 | 備考 |
> |---|---|---|
> | デジタル書斎の iOSアプリ化一式 | `digital-shosai/` | Capacitor設定・同梱PDF4冊(5.7MB)・スクショ3サイズ(8.8MB) |
> | サポート／プライバシーページ | **gh-pages** `digital-shosai-support/` | `git fetch && git log origin/gh-pages` で確認 |
> | シミュレータ操作の道具 | 直下 `simtap.py` | 初回に `~/.sim-venv` を自動で作る |
>
> **サブPCで気をつけること**
>
> - **`digital-shosai/ios/` は gitignore**。触るなら `cd digital-shosai && npm run build && npx cap add ios`
>   で作り直す。**やり直すと build番号が 1 に戻る**ので、再提出のときは必ず
>   `./ios-build-guard.sh digital-shosai` で確認してから（いま提出済みなのは **1.0.0 / build 1**）
> - **App Store への提出はメインPC限定**（配布証明書がこちらのキーチェーンにしかない）。
>   サブPCでできるのはシミュレータでの確認まで
> - `simtap.py` は**端末を変えたら `./simtap.py calib` を先に叩く**（ウインドウの倍率を実測している）
> - サブPCの Xcode は 16.1。メインPCは 26.5 なので、**iOS 26 のシミュレータは無い**はず。
>   手元にあるシミュレータで確認すればよい（アプリはiOS 15+で動く）
>
> **決着した判断（再提案しないこと）**
>
> - **App Store の著作権欄は `SHINSEI PROPERTY MANAGEMENT.K.K.`** が既定（2026-08-19 オーナー判断）。
>   メモリに「新誠プロパティマネジメント」と書いてあったのは**誤りだったので訂正済み**。
>   ただし**サポート／プライバシーページのフッターの日本語表記は別物**なのでそのままでよい
> - デジタル書斎は **iPadも対象**（`TARGETED_DEVICE_FAMILY = 1,2` のまま）

**この表だけで「いま何が進行中か」が分かるようにする。** 詳細は書かない。
詳細は各アプリの `<アプリ>/TODO.md` と `<アプリ>/SESSION_LOG.md` にある。

書き方: 1アプリ1行。終わったら行を消す（記録はアプリ側のログに残るので消してよい）。

| アプリ | 担当PC | いまの状態 / 次にやること | 最終更新 |
|---|---|---|---|
| onepiece-dex | サブ | **ワンピースカード図鑑（新規・8537・127.0.0.1）**。**2026-08-23: 立ち上げから動作確認まで完了。** 公式サイト（onepiece-cardgame.com）1本で カード4,962枚／62シリーズ／画像100%（1.2GB）。`check_dex.py` の点検は全項目0件。画面は さがす／シリーズ／リーダー の3つで、`./va.sh` で目視・Consoleエラー0件まで確認済み。**相場は未着手**（`dex.price` 列は空で用意済み。マイカのIDはゲーム横断で全ID巡回が要る）。**launchd未登録**（サブPCは都度起動）。画像の「SAMPLE」透かしは公式・マイカとも入っており消せない | 2026-08-23 |
| pokecard-dex | サブ | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え。**2026-08-19: PSAカード管理(8527)の中からも開けるようにした（実体は移していない）／メインPCで launchd 常駐に登録** | 2026-08-19 |
| psa-collection | メイン | **PSAカード管理**（旧「PSA保有カード管理」・8527）。**2026-08-19: ポケモンカード図鑑をオプションとして中から開けるようにし、アルバムに「⭐ 欲しいカード」を入れられるようにした**（バインダーは保有カードと欲しいカードを上下2枠に分離）。あわせてグレード絞り込みを削除・セット/年を「さらに絞り込む」へ格納・タイトルの絵文字を削除。次は「欲しいカード」の集計/書き出しが要るかの判断 | 2026-08-19 |
| flyer-creator | サブ | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | サブ | **完成扱いへ移行（2026-08-17）**: launchd 登録・0.0.0.0・社内LAN共有（8532）。残るのは作り込み（出来た .pptx 11枚の見栄え目視確認／字幕焼き込み／投稿API）で、通し実行はできる | 2026-08-17 |
| ai-tools-base | サブ | **AIツールベース**（https://ai-tools-base.vercel.app）。**2026-08-22（サブPC）: 9本目「Excelの行の高さを実機で採寸した」を3媒体とも公開し完了**（本体 /works/excel-row-height ／ Zenn `openpyxl-row-height-autofit` ／ note https://note.com/shinsei99/n/na1ff4ed050f4 ）。`links` 追記 → `npx vercel --prod --scope brain-dump` まで実施済み・転載⚠️は0件。**次は10本目の題材選び**（`drafts/PUBLISH.md` の順番表）。※note はサブPCからでも Chrome拡張経由で投稿できる（Playwright では不可） | 2026-08-22 |
| scrapmemo-petapeta | メイン | **2026-08-19: 保存容量の問題を根本解決し、1.0.4/build8 を審査へ提出済み。** 画像だけ IndexedDB へ移した（localStorage 5,100KB は WebKit固定／IndexedDB quota 9,830MB）。旧データは起動時に自動移行。実測で**写真30枚・77.3MB でも保持**（以前は1枚で上限）。`save()` の握りつぶしも解消し、孤児画像の掃除を追加。すべてXcodeシミュレータで実測確認済み。**次は審査結果の確認**（通ったら CLAUDE.md を「配信済み」へ）。リリースノート文案は `RELEASE_NOTES.md` | 2026-08-19 |
| digital-shosai | メイン | **2026-08-19: App Store へ審査提出済み（1.0.0/build1・`com.shinsei.shosai`・iPhone/iPad）。** Capacitor化→シミュレータで取り込み→本棚→読書→紙面→検索を通し確認→Archive→提出まで実施。**青空文庫の著作権切れ4作品を同梱**し初回起動で自動的に書斎へ入る（4冊352ページ→索引679KB）。読書画面の枠とボタンを固定、safe-area・入力欄16px未満の自動拡大によるズレも解消。スクショは3サイズ（6.9/6.5/12.9インチ）、サポート・プライバシーページは gh-pages `digital-shosai-support/` に公開。**次は ①審査結果の確認 ②実機で1度通す**（著作権欄は `SHINSEI PROPERTY MANAGEMENT.K.K.` が既定で決着）。手順は `digital-shosai/HANDOFF-APPSTORE.md` | 2026-08-19 |
| keyline | メイン | **KeyLine（NFC鍵・備品貸出管理）＋ KeyTag（iOSアプリ）。** サーバーは 8534・社内LAN限定・テスト99件成功。**2026-08-18: KeyTag を App Store へ提出**（1.0.0/build2・掲載名 KeyTagNFC・サポートページ公開済み）。**次はNFCタグ到着後の実機検証**（アプリのNFC機能は一度も実機で動かしていない）。手順は keyline/keytag/RELEASE.md | 2026-08-18 |
| chatwork-ai-manager | メイン | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中**（サブPCは常駐0本。worker・ngrokは1台のみ・同時起動禁止）。**2026-08-18: 定時TODO確認(13時/18時/翌10時等)を担当者ごとにグループ化＋TO付与する形式に修正（TASK-20260818-002・worker再起動済みで本番反映済み）。同一担当者でも一部TODOのaccount_id未解決だと別グループ・TO欠落になる不具合を修正＋名前解決の全ルーム横断フォールバックを追加（TASK-20260818-003・コミット済み・オーナー承認を得てworker再起動済み＝本番反映済み。ただし本日18時分は再起動前に実行済みのため旧仕様のまま。次回13時/18時/翌10時から新仕様）。添付Excel等の読込＋LINEからの常駐再起動も追加（TASK-20260818系）**。**2026-08-19: LINEに「処理中にエラーが発生しました: ClaudeError」が3回返った障害を調査し、原因を確定（claude CLIのOAuthトークン更新が約50分ハング＝アプリのバグではない。Keychainのmdat 09:43:03と復旧時刻が一致・実作業は18秒で残り159秒はセッション開始前に消えていた）。自然復旧済み・コードは未変更。切り分け手順は README「処理中にエラーが発生しました…」節に記載。障害中の依頼は黙って消えるので取りこぼし確認が要る。同日 TASK-20260819-001（定時TODO/週次を10:00→10:30。DB設定を実行時に読むので再起動不要・反映済み）と TASK-20260819-002（QAが未実行のTODO更新を「反映しました」と嘘をつく不具合の修正）が完了・コミット済み** | 2026-08-19 |
| ↑ chatwork-ai-manager LINE障害 | **メイン** | **2026-08-20（サブPCで対応）: 「LINEに送っても反応がない」の原因は LINEプッシュの無料枠切れ**（コミュニケーションプラン200通/月を200/200消費。LINE自身が `You have reached your monthly limit.` を返すことを実測確認）。**Chatwork側・webhook・ngrok・各トークンはすべて正常**。実測ペースは1日約50通・月約1,000通で無料枠では構造的に不足（4日で枯渇）。オーナー判断で**ライトプラン（¥5,000税別/月・5,000通）へ有料化する方針**（プラン変更は人が実行・**未実施**）。再発防止として、`line_client._post()` の失敗握りつぶしを修正・`services/line_alert.py` でChatworkへフォールバック通知・残通数の日次見張り・push呼び出し元のlabel記録 を実装しコミット済み。**★メインPCで `git pull` → worker と line_webhook の両方を再起動しないと本番に効かない（未実施）**。**メインPCでの反映手順**: `cd ~/chatwork-ai-manager && git pull` → `launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-worker` → `launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-line`（`services/line_client.py` は worker と line_webhook の**両方**が読むので片方だけでは不足）。調べた事実・確認コマンドは **`chatwork-ai-manager/README.md` の「LINEに送っても回答が返らない」節**にある（SESSION_LOG.md と TODO.md は識別子を含むため gitignore＝**メインPCには届かない**） | 2026-08-20 |
| ↑ chatwork-ai-manager 要承認 | メイン | **worker再起動の承認待ち。** TASK-20260819-002（analyzer.py/qa.py/tasks.py）に加え、TASK-20260819-003（QAのTODO一覧回答を定時確認と同じ担当者グループ化＋アイコン整形に統一。scheduler.py/qa.py/services/agent_tools/*）も稼働中workerがまだ旧コードを保持している（PID 96042・09:00:11起動 < 両タスクのコミットより前）ため未反映 | 2026-08-19 |
| ↑ chatwork-ai-manager 業務日報 | **メイン** | **2026-08-21（サブPCで実装・テスト完了）: 業務日報＋18:30の自動処理**。作成→Dropbox保管→**Chatworkへ承認なしでExcelをアップ**→**`info@daikyocorp.co.jp` へ添付メール**（オーナー依頼で追加）。承認が要るのは本文のメッセージ投稿だけ（`outbox.NEVER_AUTO_KINDS`）。**来週から本番運用**。メールは SMTP直（`smtp.daikyocorp.co.jp`・**587のみ**・STARTTLS・上限30MB。実測で確定）で、パスワードは**キーチェーン** `chatwork-ai-manager-smtp`。サブPCで認証・実送信まで確認済み（自分宛。**info@ 宛はまだ1通も送っていない**）。**★以降はメインPCで作業する。手順は `chatwork-ai-manager/README.md` 先頭の「★ メインPCで最初にやること」全8段** | 2026-08-21 |
| ↑ chatwork-ai-manager 休業日 | **メイン** | **2026-08-22（サブPCで実装・検証済み）: 会社の休業日は定時確認を送らないようにした**。8/22（土）は年間休暇スケジュールで休業日なのに 18:00 の定時確認が投稿された（休業日判定が業務日報にしか入っていなかった）。`scheduler._is_company_holiday()` を追加し、carryover_1000(10:30)／closing_1800(18:00)／due_reminder(09:00)／週次棚卸し（月・金）の claim 直後にスキップを入れた。ナレッジ増分リフレッシュ(07:00)は投稿しないので継続。休み中に期限を過ぎたTODOは翌営業日の carryover_1000（期限超過）で拾われる。**★メインPCで `git pull` → worker 再起動しないと効かない（8/23（日）も休業日なので、反映すれば投稿が止まることでそのまま検証できる）**。あわせて「朝(10:30)の定時確認が無く18:00だけ出た」理由を調べたが**サブPCからは本番DBを見られず未特定**。設計上、朝は「期限超過」か「期限未設定かつ未確認」だけが対象で、18:00 が毎晩 期限未設定を全件確認して `last_check_at` を刻むため**対象0件で無言終了するのが既定の挙動**（メインPCで `scheduled_runs` の run_date=2026-08-22 を見れば `candidates:0` かエラーかが分かる。確認コマンドは `chatwork-ai-manager/SESSION_LOG.md`） | 2026-08-22 |
| ↑ chatwork-ai-manager 商圏統計 | **メイン** | **2026-08-23（サブPCで実装・実データ検証済み）: 取得済みAPIの棚卸しから、AIが1度も呼べていなかった e-Stat（政府統計）をTool化した**。直下に共通クライアント `estat_api.py`（urllib のみ）を作り、`stats_tools.py` で4Tool追加（`estat_area_profile` / `estat_housing_profile` / `estat_indicator_search` / `estat_indicator_value`）。qa.py の system prompt にも「印象で答えず統計を引く・調査年を書く・統計の空き家は募集中の空室も含むので自社空室率とは別物」を明記。`jyuusetsu-research` の population_service も同じクライアントへ付け替え（二重実装をやめた・戻り値は不変）。**あわせて `egov_law_api.py` を requests 無しでも動くようにした**（本番の `/usr/bin/python3` に requests が無いと 8/21 の法令Toolが ImportError で落ちるため）。**★メインPCで `git pull` → worker 再起動＋`.env.estat` の受け取りが要る。`{"property":"…"}` 指定は物件マスタDBがサブPCに無く未検証なので、メインPCで1度通すこと** | 2026-08-23 |
| 買取DM／媒介契約書（住所照合） | サブ | **2026-08-23: 日本郵便APIで宛先住所を照合できるようにした**。`kaitori-dm-maker`(8526) は台帳の全宛先を一括照合し、一致／不一致／〒の補完／不明に仕分けて**問題のある宛先だけ**を出す（DMは1通ずつ郵送費がかかるため）。`baikai-generator`(8517) は依頼者（甲）の住所⇄〒をその場で照合。判定は直下の共有クライアント `japanpost_api.verify()` に集約。**実データ（実台帳）での照合はまだで、架空4件で確認しただけ**。詳細は各アプリの SESSION_LOG.md | 2026-08-23 |
| 特約条項（根拠条文の照合） | サブ | **2026-08-23: e-Gov 法令API で「引用した条文が実在するか」を確かめる層 `law_citations.py` を直下に作り、`tokuyaku-generator`(8513) に組み込んだ**。生成本文から法令引用を拾い、現行条文と突き合わせて ✅実在／⚠️見つからない／❔引けない を表示（本文は書き換えない）。**キー不要**なのでどのPCでも動く。初回は e-Gov が全文を返すため数十秒（民法1.7MB）、以降は `.egov-cache/` で速い。次の一手は「生成時に条文をプロンプトへ流し込む」 | 2026-08-23 |
| 査定／事業計画（商圏データ） | サブ | **2026-08-23: e-Stat の商圏データを直下の共有モジュール `area_stats.py` にまとめ、`realestate-valuation`(8509) と `business-plan-generator`(8533) の両方から使えるようにした**。世帯数・1世帯あたり人員・高齢化率・転入超過・空き家率・借家率・共同住宅率・着工新設貸家・2040年推計を、調査年つきで取得し**そのまま所見・前提に貼れる文**まで作る。**Excel（査定書・計画書）への出力は未実装**（今は画面＋コピー用テキストまで） | 2026-08-23 |
| jyuusetsu-research | サブ | **AI重説アシスタント**（開発中・8536予約）。**2026-08-23: 災害3項目を実装**（洪水/土砂/津波＋高潮。コード値は公式コードリストで裏取り。「区域外」と「判定不可」を分ける）。**書式の災害欄・権利部が□のチェックだった不具合を修正**（テキストを流し込むと壊れる。土砂災害の「内」だけ自動■）。**抵当権を土地／建物に分離**。**防火地域 XKT014** で取得可に。**自動入力を大幅に追加**: ①**自社情報12欄**（商号・免許・宅建士。直下 `company_profile.py`＋サイドバーで編集。**自社の立場（媒介／売主）で入れる欄を出し分け**＝宅建業者売主版はA＝売主・B/C＝媒介。**代表者・宅建士名・登録番号・地方本部は社内に記録が無く空＝要入力**）②**区域指定7種**（地区計画・都市計画道路・急傾斜地・地すべり・自然公園・立地適正化）で**64法令のうち3つを機械で■** ③**公示地価**が初めて埋まる（XPT002）④**追加資料の任意アップロード5種**（管理会社の重要事項調査報告書ほか。現状は画面表示まで）。**8517 の薄い入口の壊れも修正**。**次: ①自社情報の空欄4つを埋めてもらう ②追加資料を書式のセルへ割り当て ③4書式の印刷イメージを目視（メインPC）④実物の謄本で抵当権の振り分けを確認** | 2026-08-23 |
| tokuyaku-generator | サブ | **特約条項ジェネレーター**（8513・完成・社内LAN共有中）。**2026-08-21: 8513はこのまま恒久的に残す**（畳まない）。ただし `clauses.py` の170項目と本文生成を**共有モジュールへ切り出し**、8513 と新アプリの③タブが同じ1本を読む形にする。**コピーは禁止**（分岐すると片方だけ直した特約が契約書に載る） | 2026-08-21 |
| maisoku-converter | **メイン** | **マイソクコンバーター**（8505・社内LAN共有あり）。**2026-08-21: 帯変えモードの改修は完了**（A4縦対応／本体幅195mm・中央寄せ／白フチ自動カット既定オン／帯とのすき間4mm／帯の文字を実寸で統一）。**重大バグを1件修正: 列幅→ptの換算が2割狂っており、貼った画像が横に1.2倍伸びていた**（TwoCellAnchor→OneCellAnchor＋`_PT_PER_CHAR=6.0`。Excelで実測確認済み）。`smoke_test.py` 全項目OK・`./va.sh check` でUI崩れ0・**オーナーが画面で確認し既定値のままで確定**（紙に刷っての最終確認は未実施）。**★メインPCでやることは1つだけ: `git pull` 後に `launchctl kickstart -k gui/$(id -u)/com.shinsei.maisoku-converter`**（再起動しないと社内に修正前のコードが出続ける）。残っている課題は「帯の建設業免許番号が横向きで担当者欄へはみ出す（以前からの症状）」と「通常モード（AI解析）は用紙合わせ未対応でA4横のまま」 | 2026-08-21 |
| mail-archiver | サブ | **新規（2026-08-20）: メールアーカイバ**（IMAP容量対策・8535）。取り込み／サーバー側削除（14日＋SHA256・UIDVALIDITY・Message-ID照合＋UID EXPUNGE）／閲覧UI／偽IMAP30項目の検証。**Mail.app経由で実メール19通を取り込み確認済み。** **置き場は 原本=個人Dropbox(`Dropbox-個人/mail-archive`)・DB=ローカル固定**（同期でDBが壊れるため）。`--rebuild` でDBを原本から作り直せる（実証済み）。スマホ用に `run-lan.sh`（0.0.0.0＋`UI_PASSWORD`必須）を用意。**残り: ①iCloudのApp用パスワード発行→IMAP取り込み ②Tailscale導入（人の作業）③メインPC常駐時は/bin/bashにFDA ④restore.py** | 2026-08-20 |

## 横断作業（複数アプリにまたがるもの）

- **★ここから: 「APIの取得と整理」の再開点は `API_STATUS.md`（直下）。2026-08-20 に更新済み。**
  **この日に進んだこと**: 日本郵便が**本番**になった／用途地域のバグを修正（`XKT002`）／
  ジオコーディングを Google 併用に（ROOFTOPのときだけ）／`jyuusetsu-research` に
  ストリートビューを実装（**Webキーのリファラ制限で社内画面が403。Console設定が要る＝人の作業**）／
  直下に共通クライアント **`google_maps_api.py`** を新設。
  **e-Stat も appId を登録して実装まで完了**（`.env.estat`）。
  **e-Gov 法令API（キー不要・無料）を使える状態にした** … 共通クライアント `egov_law_api.py`。
  法令名で検索 → 条番号で本文 → キーワード検索まで実測確認（宅建業法35条・借地借家法28条）。
  **組み込み先は未着手**（`legal-crosscheck` / `tokuyaku-generator` / `gyomu-manual`）。
  **App Store Connect API を取得**（`.env.appstore` ＋ `.appstore/AuthKey_35U53KWY5J.p8`）。
  `ios-build-guard.sh` が **App Store の登録済みビルド番号**で判定するようになった。
  ★**サブPCはアーカイブ0件のため従来は誤判定していた**（scrapmemo build8 を「衝突なし」と表示）。
  ★**にゃんこのアイス屋さんは登録ビルドが0件**（「申請中」の記載と食い違う。要確認）。
  **保有APIの一覧説明書を作成** … 直下 `API一覧説明書.xlsx`（保有30件／取りに行くリスト17件／決まり9件）。
  **残りの人の作業**: 国税庁 法人番号（発行2週〜1か月・最優先）／
  App Store Connect の .p8／Maps の予算アラートとサーバーキーのIP制限。
  持っているAPIの棚卸し／未取得の一覧／朝いちで出す申請の文面／規約で不可と決めた案／
  見つかった不具合2件（用途地域が取れない・e-Statは呼ぶコードが無い）を1枚にまとめてある。
  **待ち時間のある申請（国税庁は発行2週〜1か月）を先に出すのが得。**
  受け渡しは `./secrets-sync.sh export` 済み（1.0M・28件。`.env.google-maps` と
  `.env.japanpost` の同梱を確認）。**メインPCで import → 確認 → 置き場を削除**


- **日本郵便「郵便番号・デジタルアドレスAPI」— 2026-08-20 に本番へ切り替え済み（サブPC）。**
  本番の資格情報を受領して `.env.japanpost` を差し替え、`JAPANPOST_HOST` の行を削除
  （＝既定の `api.da.pf.japanpost.jp` に向く）。疎通確認: `searchcode 5410053` → 大阪市中央区本町、
  `addresszip`（大阪市中央区・本町）→ level=3 で5件。**テスト用は `searchcode "100"` が2件、
  本番は466件**返るので、どちらに繋がっているかはこれで判る。
  テスト用stubの資格情報は `.env.japanpost.bak-stub` に退避（不要なら消してよい）。
  **★メインPCへは `./secrets-sync.sh export` で運ぶ必要がある**（キー更新のため再exportが要る）。
  以下は取得当時（2026-08-19）の記録:
  実装は直下 **`japanpost_api.py`**（`search_code` / `address_zip` / トークンのキャッシュ付き）。
  認証は OAuth2 `client_credentials`、**ヘッダ `x-forwarded-for` が必須**
  （自分のグローバルIPで通ることを実測。自動判定する作りにしてある）。
  - **本番ホストは `api.da.pf.japanpost.jp`**（モジュールの既定）。テスト用は
    `stub-qz73x.da.pf.japanpost.jp` で、**資格情報ごと別**（テスト用を本番に入れると401）。
    切り替えは `.env.japanpost` の `JAPANPOST_HOST` 1行（**本番が出たらこの行を消す**）
  - 疎通確認済み: `searchcode "100"` → 千代田区 内幸町/大手町。
    `addresszip 13/13101` → level=2 で6件。カナ・ローマ字も返る
  - ~~★人がやること: 本番用の組織・システム登録 → 本番のクライアントID／シークレットの発行~~
    → **2026-08-20 に完了**（差し替え済み）
  - **未確認**: レート制限の具体的な数値。テスト用は「予告なくデータのクリーンアップ・処理中断」
    があり、負荷試験や大量利用は不可
  - 使い道: `soufu-maker` / `kaitori-dm-maker` / `tsuikyaku-crm` の住所正規化。
    **v2.0 では法人名・電話番号・法人番号まで取れる**ので、法人番号APIの前段にもなる

- **Google Maps / ストリートビュー API を取得した（2026-08-19・サブPC）。詳細は `GOOGLE_MAPS_API.md`。**
  プロジェクト **`daikyo-maps-2026`**（**Gemini とは別プロジェクト**。同じだと公開ページに載せた
  キーで Gemini を叩かれるため）。請求先は Gemini と同じ口を流用＝**カード再入力なし**。
  キー2本は **`.env.google-maps`（直下・gitignore・600）**。`secrets-manifest.txt` に登録済み。
  **Geocoding と Street View は実際に叩いて動作確認済み**（本町4-2-12 / 2021-08撮影のパノラマ）。
  - **★メインPCでやること: `./secrets-sync.sh import` で受け取る。**
    置き場 `Dropbox-個人/apps-secrets-handoff/apps-secrets-appurunoMacBook-Air.tar`（980K・27件）。
    **受け取りを確認したら、置き場ごと削除する**（消すのは受け取った人）
  - 未了: サーバー用キーの**IP制限**（事務所の固定IPが不明）／**予算アラートと日次クォータ**／
    Drive API は有効化しただけで **OAuth同意画面の設定が未了**
  - 規約で**不可**になった案: `parking-map` の航空写真トレース（3.2.3(c)(i)）と
    `kaitori-dm-maker` のSV外観AI判定（3.2.3(c)(vii)）。**SVは印刷物にも使えない**
  - ~~次の一手: `jyuusetsu-research` にストリートビュー~~ → **2026-08-20 実装済み**。
    ただし **Webキーのリファラ制限（`https://daikyocorp.co.jp/*` のみ）で社内画面は 403**。
    **人がやること**: Console で「Maps Embed だけに絞ったキー」を新規作成し社内画面用に使う
    （埋め込みは無制限無料なので、漏れても課金されない）。詳細は `jyuusetsu-research/README.md`
  - 直下に共通クライアント **`google_maps_api.py`** を新設（`japanpost_api.py` と同じ置き方）。
    `geocode` / `streetview_metadata` / `streetview_embed_url` / `map_embed_url`。
    **`.gitignore` に `!google_maps_api.py` の許可行が要る**（追加済み）

- **iOSシミュレータを操作する道具を直下に置いた（`simtap.py`・2026-08-19）。**
  `xcrun simctl` にはタップが無いので、画面を見て直ったか確かめられなかった。
  `./simtap.py calib / tap x y / drag x y1 y2 / type "文字" / key return` で操作できる
  （初回に `~/.sim-venv` を自動で作る）。**日本語は `keystroke` だと化ける**ので
  クリップボード経由で入れている。`.gitignore` に `!simtap.py` の許可行も入れた

- ~~**★ 8/19 にやること: KeyLine の Zenn と note を「まとめて」出す**~~ ✅ **2026-08-19 完了（サブPC）**。
  本体はもう公開済み → https://ai-tools-base.vercel.app/works/keyline
  1. **20:47 以降**に `cd ai-tools-base && ./publish.sh zenn` → `./publish.sh status` が ✅ になるまで確認
  2. ✅ を見てから `python3 drafts/note/md2html.py who-has-the-key` → note の本文欄で ⌘V → 投稿
  3. `content/works/keyline.json` の `links` に2本のURLを足して `./publish.sh site`
  **手順の詳細と「なぜ20:47以降なのか」は `ai-tools-base/drafts/PUBLISH.md` の8本目の節にある。**
- **`./publish.sh zenn` は空コミットを作らない。** `articles/` に変更が無いと `git commit` が失敗し、
  `git push` が "Everything up-to-date" で終わって **Zenn のデプロイが走らない**。
  弾かれた1本を再pushするときは、先に `git commit --allow-empty` を叩くこと（8/19に実測）
- **Zenn の上限本数は公開されていない**（2026-08-19に公式FAQで確認）。「1日2本」はこちらの推測だった。
  判定は「直近24時間以内の投稿数」だが、**本数のロジックは不正防止のため非開示**
  （https://zenn.dev/faq/rate-limit）。実際 8/19 は**直近24時間の公開が1本だけ**の状態で
  2本目が弾かれた。**本数で予定を組まず、毎回 `./publish.sh status` とデプロイ履歴で確かめる**
- （参考・8/18の事例）**「pushした本数」ではなく「直近24時間に公開された本数」で数えられる**。
  メインPCが前日pushした `llm-pdf-split-gaps` の反映が 8/18 20:47 だったため、その日の枠を消費し、
  3本目の `ios-nfc-safari-entitlement` が弾かれた。**デプロイ履歴のお知らせ欄に理由が明記される**
  （https://zenn.dev/dashboard/deploys ・要ログイン）。`./publish.sh status` の ⬜ でも検知できる
- **note はこのサブPCからも投稿できる**（8/18に実測）。Chrome拡張が繋がり、noteはログイン済み。
  **拡張が「未接続」と出たら、Chrome を前面に出せば繋がる**（起動していても最前面でないと繋がらない）
- **Zenn 7本 / note 7本で揃っている**（2026-08-19 22:36時点）。残りは `ai-intake-hearing`（Zenn）と
  `nanka-ugokanai`（note）の1組だけ。**Zenn→note の順で、対にして出す**
- **公開状況は推測で書かない。** note は API
  （`https://note.com/api/v2/creators/shinsei99/contents?kind=note&page=N`・1ページ6件）、
  Zenn は `./publish.sh status` で確かめてから書く。2026-08-19 に
  「note は6本とも未公開」という記述が誤りだったことが実測で判明している
- **note の見出し画像は「この画像を挿入」のあとに出る「保存」まで押す。** 押さないと入らない
  （2026-08-19 に2回とりこぼした）。貼ったあとは画像を目で見る（「書類の山」で検索して
  出てきた画像が実際は札束だった）
- **共通 Visual Agent を1つに統合した（2026-08-18・メインPC）。** 2台が別々に作った
  MCP版（`.mcp.json`）と `./va.sh` を、**1つの仕組み・2つの入口**に整理。どちらも消していない。
  - **同じ Google Chrome を headless で開く**ようにしたので、入口が違っても見えるものが食い違わない
  - `./va.sh` の Playwright は `VA_PYTHON` → `agent-platform/.venv` → `.va-venv` → `python3`
    の順に探す。**agent-platform 決め打ちをやめた**ので、あのアプリが無いPCでも動く
  - `./visual-agent-check.sh` が**両方の入口**を点検する（`--mcp` / `--va` で片方だけも可）
  - 説明は `VISUAL_AGENT.md` 1本に集約（CLAUDE.md は要点だけ）
  - **`.mcp.json` はもともと git に入っていた。** サブPCに届いていなかったのは、メインPCが
    27コミットを push していなかったから。→ サブPCは `git pull` だけで入口Aも使えるようになる
  - メインPCで実測: 入口A・入口Bとも「開く→押す→読む→撮る→check」まで成功（2026-08-18）
- **`dev-doctor.py --sync` が出す「gitに入っていないソース候補 1件」＝ `make_app_list.py`。**
  2026-06 の使い捨てスクリプト（社内アプリ一覧のExcelを吐く）で、**社内ホスト名とportを直書き
  している**。リポジトリは公開なので**意図的に git に入れない**。中身は CLAUDE.md のアプリ表が
  正なので、必要になったら作り直す。＝この警告は既知・対応不要（毎回調べ直さない）
- **見つかった未修正のUI崩れ（ai-tools-base・390px幅）**: 比較表が横に484pxはみ出していて
  料金列が読めない（`div.table-scroll` は `overflow-x:auto` だが手がかりが無い）。ロゴも2行に折れる
- **3媒体への公開は、3つともサブPCからできる**（8/18・8/19に実測）。以前「メインPC担当」と
  書いていたが、サブPCにも Chrome拡張・note/Zenn のログイン・Vercel の認証がある。
  **Vercel 本番デプロイも 2026-08-19 にサブPCから成功した。**
  - ただし1回目は `Not authorized` で失敗した。原因は `.vercel/project.json` の `projectName` が
    **旧名 `ai-tools-lab` のまま**だったこと（`.vercel/` は gitignore なので git では直らない）。
    `npx vercel link --yes --project ai-tools-base --scope brain-dump` で直る
  - **`./publish.sh site` の「反映確認」を信用しない。** デプロイが失敗しても既存デプロイに
    当たって HTTP 200 と出る。**`Aliased …` の行と、実際のページの中身で確かめる**
  手順は `ai-tools-base/drafts/PUBLISH.md`、入口は `ai-tools-base/publish.sh`
- ~~ai-tools-base のフォルダ改名の後始末（node_modules 等の移動）~~ → **2026-08-18 完了**
  （`ai-tools-lab` は削除済み。実体は `ai-tools-base/` にある）
- ~~`digital-shosai/.env.local` が不足~~ ✅ **そもそも不要だった**（2026-08-17実測）。完全オンデバイス版
  （pdf.js＋IndexedDB）に作り替えられており `process.env` の参照が0件。旧設計の `.env.local.example` を
  削除し manifest からも外した。→ **機密の不足は0件になった**
- ~~サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）~~
  ✅ 2026-08-17 に unload 済み。サブPCの launchd 常駐は**0本**（`launchctl list | grep shinsei` が空）。
  画面が要るときは `cd <アプリ> && ./run.sh` で都度起動する（常駐に戻さない）

- ~~CLAUDE.md のスリム化~~ ✅ **2026-08-17にサブPCで実施**。**27,288字 → 14,700字（46%削減）**。
  アプリ個別の補足 12,999字を10本の `<アプリ>/README.md` へ移し、CLAUDE.md にはポインタ一覧だけ残した
  （移動先: gyomu-manual / parking-map / kaitori-dm-maker / psa-collection / agent-platform /
  chatwork-ai-manager / flyer-creator / shorui-cabinet / photo-inpainter / theta-viewer）。
  **`quote-generator` だけは別リポジトリでREADMEが渡らないため CLAUDE.md に残した。**
  なお「`photo-inpainter/` `pdf-organizer/` はフォルダごと無視されてREADMEが渡らない」という
  以前の注意書きは**古い情報だった**（`!photo-inpainter/**` の許可行が既にあり、渡ることを実測）。
- **agent-platform をメインPCで動かすには別途ファイルが要る**（gitに入れていない）:
  `config/`（会社名・免許番号などの発行者情報）、`knowledge/`（学習データ。物件名が混ざる）、
  `.env`（`.env.example` をコピーしてGeminiキーを入れる）。Dropbox等で渡す。
