# TODO — 全アプリの索引

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
> **⑤ AIツールベースの note 1本が未公開のまま**（`ai-ticket-counter` の `nanka-ugokanai`）。
> **このサブPCでは自動投稿できない**と判明: MCPは拡張ではなくPlaywrightで `--isolated --headless`
> ＝ログインが残らず、headedで開くと **note がボット検知でブロック**（回避はしない方針）。
> Chrome拡張は入っていて有効・claude.aiもログイン済みだが**接続だけ通らない**（未解決）。
> → **手貼りか、メインPCで出すのが早い。** 詳細は `ai-tools-base/SESSION_LOG.md` の 2026-08-21 の節。
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
| pokecard-dex | サブ | 画像100%（31,520枚）。内訳に推定14枚・参考画像4枚・透かし2枚あり。次はそれらの実物差し替え。**2026-08-19: PSAカード管理(8527)の中からも開けるようにした（実体は移していない）／メインPCで launchd 常駐に登録** | 2026-08-19 |
| psa-collection | メイン | **PSAカード管理**（旧「PSA保有カード管理」・8527）。**2026-08-19: ポケモンカード図鑑をオプションとして中から開けるようにし、アルバムに「⭐ 欲しいカード」を入れられるようにした**（バインダーは保有カードと欲しいカードを上下2枠に分離）。あわせてグレード絞り込みを削除・セット/年を「さらに絞り込む」へ格納・タイトルの絵文字を削除。次は「欲しいカード」の集計/書き出しが要るかの判断 | 2026-08-19 |
| flyer-creator | サブ | チラシクリエーター。型10種はagent-platform共通（直すのはagent-platform/core）。下帯ロゴ＋メイン写真の切取位置(上下)スライダー追加。次は物件データの未決3点 | 2026-08-16 |
| agent-platform | サブ | **完成扱いへ移行（2026-08-17）**: launchd 登録・0.0.0.0・社内LAN共有（8532）。残るのは作り込み（出来た .pptx 11枚の見栄え目視確認／字幕焼き込み／投稿API）で、通し実行はできる | 2026-08-17 |
| ai-tools-base | サブ | **AIツールベース**（https://ai-tools-base.vercel.app）。**2026-08-19（サブPC）: Zenn 7本 = note 7本に揃えた**（KeyLine の Zenn/note に加え、note を4本まとめて公開）。`links` も6件ぶん追記し、`npm run validate` の転載⚠️は **ai-ticket-counter の1件だけ**。**本番反映済み（8/19・サブPCから `./publish.sh site` 成功。/works/keyline 等でリンク表示を確認）。次は ①Zenn `ai-intake-hearing` を空コミットで再push（8/19 22:35 の push は上限で弾かれた）②Zennが✅になってから note `nanka-ugokanai`** | 2026-08-19 |
| scrapmemo-petapeta | メイン | **2026-08-19: 保存容量の問題を根本解決し、1.0.4/build8 を審査へ提出済み。** 画像だけ IndexedDB へ移した（localStorage 5,100KB は WebKit固定／IndexedDB quota 9,830MB）。旧データは起動時に自動移行。実測で**写真30枚・77.3MB でも保持**（以前は1枚で上限）。`save()` の握りつぶしも解消し、孤児画像の掃除を追加。すべてXcodeシミュレータで実測確認済み。**次は審査結果の確認**（通ったら CLAUDE.md を「配信済み」へ）。リリースノート文案は `RELEASE_NOTES.md` | 2026-08-19 |
| digital-shosai | メイン | **2026-08-19: App Store へ審査提出済み（1.0.0/build1・`com.shinsei.shosai`・iPhone/iPad）。** Capacitor化→シミュレータで取り込み→本棚→読書→紙面→検索を通し確認→Archive→提出まで実施。**青空文庫の著作権切れ4作品を同梱**し初回起動で自動的に書斎へ入る（4冊352ページ→索引679KB）。読書画面の枠とボタンを固定、safe-area・入力欄16px未満の自動拡大によるズレも解消。スクショは3サイズ（6.9/6.5/12.9インチ）、サポート・プライバシーページは gh-pages `digital-shosai-support/` に公開。**次は ①審査結果の確認 ②実機で1度通す**（著作権欄は `SHINSEI PROPERTY MANAGEMENT.K.K.` が既定で決着）。手順は `digital-shosai/HANDOFF-APPSTORE.md` | 2026-08-19 |
| keyline | メイン | **KeyLine（NFC鍵・備品貸出管理）＋ KeyTag（iOSアプリ）。** サーバーは 8534・社内LAN限定・テスト99件成功。**2026-08-18: KeyTag を App Store へ提出**（1.0.0/build2・掲載名 KeyTagNFC・サポートページ公開済み）。**次はNFCタグ到着後の実機検証**（アプリのNFC機能は一度も実機で動かしていない）。手順は keyline/keytag/RELEASE.md | 2026-08-18 |
| chatwork-ai-manager | メイン | Chatwork/LINE常駐AIエージェント（社内RAG・TODO/案件・Web/国交省API）。**常駐4サービスはメインPCで稼働中**（サブPCは常駐0本。worker・ngrokは1台のみ・同時起動禁止）。**2026-08-18: 定時TODO確認(13時/18時/翌10時等)を担当者ごとにグループ化＋TO付与する形式に修正（TASK-20260818-002・worker再起動済みで本番反映済み）。同一担当者でも一部TODOのaccount_id未解決だと別グループ・TO欠落になる不具合を修正＋名前解決の全ルーム横断フォールバックを追加（TASK-20260818-003・コミット済み・オーナー承認を得てworker再起動済み＝本番反映済み。ただし本日18時分は再起動前に実行済みのため旧仕様のまま。次回13時/18時/翌10時から新仕様）。添付Excel等の読込＋LINEからの常駐再起動も追加（TASK-20260818系）**。**2026-08-19: LINEに「処理中にエラーが発生しました: ClaudeError」が3回返った障害を調査し、原因を確定（claude CLIのOAuthトークン更新が約50分ハング＝アプリのバグではない。Keychainのmdat 09:43:03と復旧時刻が一致・実作業は18秒で残り159秒はセッション開始前に消えていた）。自然復旧済み・コードは未変更。切り分け手順は README「処理中にエラーが発生しました…」節に記載。障害中の依頼は黙って消えるので取りこぼし確認が要る。同日 TASK-20260819-001（定時TODO/週次を10:00→10:30。DB設定を実行時に読むので再起動不要・反映済み）と TASK-20260819-002（QAが未実行のTODO更新を「反映しました」と嘘をつく不具合の修正）が完了・コミット済み** | 2026-08-19 |
| ↑ chatwork-ai-manager LINE障害 | **メイン** | **2026-08-20（サブPCで対応）: 「LINEに送っても反応がない」の原因は LINEプッシュの無料枠切れ**（コミュニケーションプラン200通/月を200/200消費。LINE自身が `You have reached your monthly limit.` を返すことを実測確認）。**Chatwork側・webhook・ngrok・各トークンはすべて正常**。実測ペースは1日約50通・月約1,000通で無料枠では構造的に不足（4日で枯渇）。オーナー判断で**ライトプラン（¥5,000税別/月・5,000通）へ有料化する方針**（プラン変更は人が実行・**未実施**）。再発防止として、`line_client._post()` の失敗握りつぶしを修正・`services/line_alert.py` でChatworkへフォールバック通知・残通数の日次見張り・push呼び出し元のlabel記録 を実装しコミット済み。**★メインPCで `git pull` → worker と line_webhook の両方を再起動しないと本番に効かない（未実施）**。**メインPCでの反映手順**: `cd ~/chatwork-ai-manager && git pull` → `launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-worker` → `launchctl kickstart -k gui/$(id -u)/com.shinsei.chatwork-ai-manager-line`（`services/line_client.py` は worker と line_webhook の**両方**が読むので片方だけでは不足）。調べた事実・確認コマンドは **`chatwork-ai-manager/README.md` の「LINEに送っても回答が返らない」節**にある（SESSION_LOG.md と TODO.md は識別子を含むため gitignore＝**メインPCには届かない**） | 2026-08-20 |
| ↑ chatwork-ai-manager 要承認 | メイン | **worker再起動の承認待ち。** TASK-20260819-002（analyzer.py/qa.py/tasks.py）に加え、TASK-20260819-003（QAのTODO一覧回答を定時確認と同じ担当者グループ化＋アイコン整形に統一。scheduler.py/qa.py/services/agent_tools/*）も稼働中workerがまだ旧コードを保持している（PID 96042・09:00:11起動 < 両タスクのコミットより前）ため未反映 | 2026-08-19 |
| jyuusetsu-research | サブ | **AI重説調査〜Excel自動入力**（開発中・launchd未割当）。**2026-08-20: 用途地域が常に空だったのを修正**（`XKT001`→**`XKT002`**＋プロパティ名・単位・最寄り代用の100m上限）。ジオコーディングを Google 併用に（`location_type` が ROOFTOP のときだけ採用。加東市で Google が892m外した実測あり）。ストリートビューの節を追加。**e-Statの人口・世帯数も実装済み**（統計表0000020101／A1101・A7101／市区町村コードは国土地理院）。**次は ①Webキーのリファラ制限で社内画面が403 → Console で「Maps Embed だけに制限したキー」を作り `.env.google-maps` に `GOOGLE_MAPS_EMBED_KEY=` を追記（人の作業。コードは対応済み）** | 2026-08-20 |
| maisoku-converter | サブ | **マイソクコンバーター**（8505・社内LAN共有あり）。**2026-08-20: 帯変えモードの切り取り枠をプレビュー上で直接ドラッグ移動・サイズ変更できるようにした**（新規 `crop_component/`。スライダー4本と双方向同期・リセット付き）。続けて「細かく調整できない」対応として **刻みを0.005→0.001／プレビューを最大1600pxまで拡大（1200以上でスライダーが上段に移り全幅表示・実測926→1198px）／つかんでいる間の拡大鏡×3.5／■選択後に矢印キーで1ドット送り（Shiftで10）／px併記** を追加。検証は合成テスト画像でPlaywright（枠⇄スライダー・拡大鏡・矢印キー・リセット・Excel生成／Consoleエラー0件）。次は ①実物の他社マイソクPDFで一度通す ②通常モード（AI解析）の切り抜きにも同じ枠エディタを使う | 2026-08-20 |
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
