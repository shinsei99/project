# SESSION LOG — 横断作業

**1つのアプリで完結する作業のログはここに書かない。** それは
`<アプリ>/SESSION_LOG.md` に書く（例: `pokecard-dex/SESSION_LOG.md`）。

ここに書くのは、複数のアプリにまたがる作業だけ。
ポート割り当ての変更、launchd の整理、共通モジュール（`pdf_orient.py` など）の変更、
`.gitignore` や公開方法の方針変更、といったもの。

新しい節は**このすぐ下に追記**する（上が新しい）。書式は `CLAUDE.md` の作業ルール参照。

---

## 2026-08-19（サブPC）— Google Maps / ストリートビュー API を入れるかの裏取り

### 完了したこと

- **契約前の判断材料として、料金体系と利用規約を一次情報（Google公式）で確認し、
  `GOOGLE_MAPS_API.md`（直下）にまとめた。** まだキーは取っていない・契約もしていない
- 分かったことの要点:
  - **料金**: 旧「$200/月クレジット」は 2025-03-01 に廃止され、**APIごとの月次無料枠**へ
    （枠は合算されない）。**Embed（埋め込み）は無制限・無料**。社内利用の規模なら実質 $0
  - **キー取得にはクレジットカードが要る**。ただし **Maps Demo Key はカード不要**
    （日次上限つき・本番不可）なので、試すだけならカードなしで始められる
  - **規約で前回の案が2つ死んだ**: ①航空写真をなぞって駐車場配置図を作る（`parking-map`）は
    3.2.3(c)(i) で明確に禁止 ②ストリートビューをAIに読ませて空き家判定（`kaitori-dm-maker`）は
    3.2.3(c)(vii) のAI条項に抵触する
  - **ストリートビューは印刷物に一切使えない**（Geo Guidelines）。地図（Maps）は
    販促物5,000部まで・帰属表示必須なら可 → **紙チラシの案内図は作れる**
  - **ストリートビューと非Googleの地図は同一画面に出せない**（3.2.3(e)(ii)）。
    `jyuusetsu-research` / `legal-crosscheck` は地理院地図を出しているので**別タブに分ける**
- **既存の無料実装を確認した**（重複投資を避けるため）。住所→緯度経度と最寄駅は
  国土地理院＋HeartRails で**すでに無料・キー不要で動いている**（`geo_service.py` /
  `address_service.py`）。Google に払う価値があるのは**ストリートビュー・Places・道路距離**だけ

### 発生したエラーと解決策

- 規約ページを WebFetch すると本文が長すぎて途中で切れ、条項を引用できなかった
  → `curl` で HTML を落とし、タグを剥がして条項名で grep する方式に切り替えて取得した
- **新規作成した `GOOGLE_MAPS_API.md` が `.gitignore` の `*` で無視されていた**（既知の落とし穴）
  → 許可行 `!GOOGLE_MAPS_API.md` を追加。`git add -n` で追跡できることまで確認した

### 追記（同日・キーの取得まで完了した）

- **gcloud CLI を導入した**（581.0.0）。`~/.local/google-cloud-sdk`・**sudo不要**（`gh`と同じ流儀）。
  **gcloud は Python 3.10〜3.14 が要る**（`/usr/bin/python3` は 3.9.6 で動かない）ので、
  brew の `python3.11` を `CLOUDSDK_PYTHON` で指す設定を `~/.zshrc` に入れた
- **Cloud プロジェクト `daikyo-maps-2026` を作り、Gemini と同じ請求先を紐づけた**（カード再入力なし）。
  **Gemini とは別プロジェクトにした**のが要点 — Generative Language API が有効なプロジェクトでは
  **既存のAPIキー全部が Gemini にも通る**ため、公開ページに載せる Maps キーと同居させられない
- **キー2本を発行**（公開ページ用＝リファラ制限 / サーバー用＝API種別制限）。
  値は画面に出さず `.env.google-maps`（600）へ直接書き、`secrets-manifest.txt` に登録
- **実際に叩いて確認した**: Geocoding は `status: OK`（本町4-2-12 → 34.6833416, 135.5001744）、
  Street View metadata も `status: OK`（**2021-08 撮影のパノラマあり**）
- **Maps API / Drive API を有効化**（Embed / Street View Static / Geocoding / Directions / Static Maps ＋ Drive）
- `./secrets-sync.sh export` でメインPCへ渡す tar を作成（980K・27件。`.env.google-maps` の同梱を確認）

### 発生したエラーと解決策（追記分）

- `gcloud` が Python 3.9 で `TypeError: unsupported operand type(s) for |` を吐いて起動しない
  → gcloud 581 は Python 3.10〜3.14 必須。brew の 3.11 を `CLOUDSDK_PYTHON` に指定して解決
- `~/.zshrc` に PATH を追記しても、**すでに開いているシェルには効かない** → フルパスで叩いた

### 追記2（同日・日本郵便のAPIも疎通まで進めた）

- **共通クライアント `japanpost_api.py` を直下に作った**（`search_code` / `address_zip` /
  トークンのキャッシュ）。複数アプリ（`soufu-maker` / `kaitori-dm-maker` / `tsuikyaku-crm`）から
  住所の正規化に使うため、**1本だけ置いて共有する**（`pdf_orient.py` のようにコピーを増やさない）
- **テスト用の資格情報で疎通を確認した**: トークン発行 → `searchcode "100"` で
  千代田区 内幸町/大手町、`addresszip 13/13101` で level=2 の6件。カナ・ローマ字も返る
- **本番とテストはホストも資格情報も別**。本番 `api.da.pf.japanpost.jp` にテスト用の
  クライアントIDを入れると **401**（実測）。切り替えは `.env.japanpost` の `JAPANPOST_HOST` 1行
- **`x-forwarded-for` は自分のグローバルIPで通る**（`api.ipify.org` で自動判定して控える作りにした）
- Chrome拡張が未接続でブラウザ操作はできなかった（ポータルは本人が操作）

### 次回への引き継ぎ事項・未解決の課題

- **日本郵便は本番の資格情報が未発行。** ポータルで組織・システム登録が要る。
  届いたら `.env.japanpost` を差し替え、`JAPANPOST_HOST` の行を消す
- **サーバー用キーに IP 制限が未設定**（事務所の固定グローバルIPが不明）。分かり次第かける
- **予算アラート・日次クォータが未設定。** Gemini と同じカードなので合算で請求が来る
- **Drive API は有効化しただけ**。使うには OAuth 同意画面の設定が要る
- **★メインPCで `./secrets-sync.sh import` → 受け取り確認 → Dropboxの置き場を削除**
- 国税庁・日本郵便のAPIは**本人申請が必要**なので未取得（TODO.md の横断作業を見る）
- ~~Demo Key で Street View が試せるか未確認~~ → **通常キーを取得したので不要になった**
- **次の一手**: `jyuusetsu-research` に別タブでストリートビュー
  （公開課金なし・印刷なし＝規約リスクが最も低い）。手順は `GOOGLE_MAPS_API.md` の「4. 使う順」

## 2026-08-18（サブPC）— メインPCからの引き継ぎを受領し、依頼①〜④を実行した

### 完了したこと

- `git pull origin main` で **48コミット**を fast-forward 取り込み（未コミット0・ローカル先行0）。
  統合版 Visual Agent / KeyLine・KeyTag / chatwork の新機能 が届いた
- `./visual-agent-check.sh` … **入口A（MCP）・入口B（`./va.sh`）とも全項目 ✅**。
  同じ Google Chrome を headless（CDP 9223）で開くところまで実測（撮影 `.see/0818-212350-va-check.png`）
- `./secrets-sync.sh import` … メインPC発（2026-08-18 12:33）の tar から **`keyline/data` を取り込み**
  （keyline.db 180KB ＋ id_images）。残り12件は既存のため据え置き。**機密の不足は 0 件**になった
- `./secrets-sync.sh export` … サブPC側の18件を書き出し（980K）。
  `Dropbox-個人/apps-secrets-handoff/apps-secrets-appurunoMacBook-Air.tar` に置いた
- **メモリ実体20本**を `Dropbox-個人/handoff-20260818-sub-to-main-2/memory/` に配置（**20/20・168K**）
- **メインPCが「未確認」としていた点を確認: このサブPCに Xcode 16.1 (16B40) が入っている。**
  KeyTag のビルドは可能（ただし配布証明書が無いので**提出はメインPC限定**のまま変わらない）

### 発生したエラーと解決策

- 症状: `./dev-setup.sh --all` が対象0本のとき `list[@]: unbound variable` で異常終了した
  → 原因: macOS の bash 3.2 は `set -u` 下で**空配列の `"${arr[@]}"` 展開を未定義変数とみなす**
  （bash 4.4 以降は許容するため、書いた環境では再現しない）
  → 直し方: `${list[@]+"${list[@]}"}` 形式に変更（`TARGETS` 側も同様）。対象0本でも exit 0 で完走を確認

### 追記2（同日夜・新規1本を3媒体へ）

**KeyLine の制作記録を新規作成し、3媒体ぶんの原稿を書いた**（本体・Zenn・note）。

- 本体 `content/works/keyline.json` … **本番へ公開済み**
  https://ai-tools-base.vercel.app/works/keyline （HTTP 200・title も確認）
  検証は `npm run lint` / `npm run build` / `npm run validate` を通し、
  **`./va.sh` で 390 / 768 / 1440 の3幅を撮って目視**（はみ出し・文字の重なり **0件**）
- Zenn `articles/ios-nfc-safari-entitlement.md` … **push 済みだが、まだ反映されていない**（下記）
- note `drafts/note/who-has-the-key.md` … 原稿と貼り付け用テキストまで用意。**投稿は未**

題材は「SafariはWeb NFCに非対応 → タグにURLを書く方式へ切り替えた」。
**実機検証が未了であることは3媒体すべてに明記した**（「動くはず」で書かない）。

### 発生したエラーと解決策（追記2）

- 症状: Zenn へ push しても記事が増えない（API の公開数が 6 のまま）
  → 原因: **投稿数の上限。デプロイ履歴のお知らせ欄で確定した**（文言: 「次の記事は投稿数の上限に
  達したためデプロイされませんでした: ios-nfc-safari-entitlement」）。Zenn は上限に当たると
  **黙ってデプロイしない**（push自体もデプロイ表示も「成功」になる）
  → **重要: 上限は「自分がpushした本数」ではなく「直近24時間に公開された本数」で数えられる。**
  `llm-pdf-split-gaps` はメインPCが前日 push したものだが、**Zenn側の反映が 8/18 20:47** だったため
  この日の枠を1本消費していた。そこへ 21:32 の1本が入って2本になり、3本目が弾かれた
  → 直し方: **最も古い1本が24時間の窓から外れてから再push**（＝8/19 20:47以降）。自動再試行は無い
- 症状: Chrome拡張（Claude in Chrome）が「未接続」と出て、note の投稿操作ができない
  → 原因: **Chromeは起動していたが最前面ではなかった**。プロセスがあるだけでは繋がらない
  → 直し方: `open -a "Google Chrome"` で前面に出すと即座に接続された（`list_connected_browsers`
  が空 → 1件に変わる）。**note はログイン済みで、サブPCからも投稿できることを実測**
  （「メインPC担当」という以前の前提は、この点については古い）

### 判断（本人・2026-08-18 夜）

- **KeyLine の Zenn と note は、8/19 にまとめて出す。** noteの本文にZennのURLが入っているため、
  Zennが通る前にnoteを出すとリンク切れになる。今日は本体の公開までで止める

### 追記（同日夜・本人の指示で実行）

- **Zenn: `scanned-pdf-orientation` を公開した**（21:32）。`llm-pdf-split-gaps` は 20:47 に
  反映済みだったので、**この日の枠（1日2本）を使い切った**。
  → https://zenn.dev/shinsei99/articles/scanned-pdf-orientation （HTTP 200・API でも最新として確認）
  公開前に、本文中の本体リンク（`/works/baikai-generator`）が HTTP 200 であること、
  slug が規約内（23字・半角英小文字とハイフン）であることを確認している。
  **Zenn は原稿7本中6本が公開済み。残りは `ai-intake-hearing` 1本だけで、8/19 以降**
- **stash とローカルブランチを破棄した**（復元用SHA: stash `9812065` / branch `b507e7c`。reflog にも残る）
- **メインPC発の機密 tar を Dropbox から削除した。** 中身13件すべてが手元に実体としてあることを
  1件ずつ確認してから消している。**サブPC発の tar とメモリ20本は残してある**（メインPCが未受領のため）

### 発生したエラーと解決策（追記）

- 症状: `./publish.sh zenn` が push 成功後に `before?: unbound variable` で異常終了した
  → 原因: `echo "（push前の公開数: $before）"` の**全角の閉じ括弧が変数名の一部として解釈**されていた。
  bash はマルチバイトのバイトを識別子の文字として受け入れるため、`$before）` という別の変数を探しに行く
  → 直し方: `${before}` と明示的に囲んだ。push 自体は成功していたので公開への影響は無し

### 次回への引き継ぎ事項・未解決の課題

- ~~stash とローカルブランチ~~ → **同日夜に破棄済み**（下の判断根拠はそのまま残す）
  - `stash@{0} pre-origin-sync` … 中身は**未追跡ファイルのみ**（handwriting-ocr 4本 / piyo-defense/ios）。
    handwriting-ocr は現在 git 管理下にあり、`ocr.py`・`requirements.txt` は**作業ツリーのほうが新しい**
    （6/30 の pdf_orient 対応版 > stash の 6/26 版）。＝復元すると**古い版に戻る**ので取り込んではいけない
  - `pre-sync-backup-20260626` … main に無い固有コミットは `b507e7c color-gravity` の1件だけで、
    同じ内容が **PR #1（`f83dedf`）として main に入っている**。＝残す理由は無い
- 残っているもの: **Zenn 最後の1本 `ai-intake-hearing`（8/19以降・上限のため）**、
  **note 5本（ブラウザ操作＝メインPC担当）**、**デジタル書斎の App Store 提出（メインPCのみ）**

---

## 2026-08-18（メインPC・続き）— 2台の環境差を詰め、依頼3件を実装した

### 完了したこと

- **メインPCの依存不足8本を解消**（handwriting-ocr / legal-crosscheck / memorandum-generator /
  parking-map / pasha-calo / payment-reconciler / property-notice-generator / quote-generator）。
  `./dev-setup.sh --all` の対象が **0本**になり、サブPC（31/31・14/14）と同水準になった
- **点検ツールの穴を2つ塞いだ**
  - `dev-doctor.py` のアプリ表に **keyline が入っていなかった**（不動産31本と表示されていた→32本）
  - `keyline/requirements.txt` を新設（fastapi / uvicorn / python-multipart）。無かったため
    「static・依存不要」と誤判定され、**他PCでは依存が入らないまま**になっていた。
    `NO_VENV` に keyline を追加（OCRで claude を呼ぶので venv を使わない決まり）
  - `dev-setup.sh --all` の判定が `"$app" != "$NO_VENV"` の単純比較で、NO_VENV が2つ以上に
    なった瞬間に壊れる書き方だった。`pip install --user` 済みも「導入済み」と見るよう修正
- **KeyTag の渡し方を直した**（サブPCへ引き継ぐ前提で点検して見つけた）
  - `keytag/build/` `build-sim/` が誤って追跡され、**195MB・2,439ファイルが公開リポジトリに**
    入っていた（xcarchive の `embedded.mobileprovision` 含む）。追跡から外した。
    **履歴からは消さない判断**（本人決定。理由は `keyline/keytag/RELEASE.md`）
  - `ios/` は gitignore のため、他PCで作り直すと **build番号が1に戻る**（7/22の配信事故と同型）。
    → `keytag/version.json` を版数の正とし、`setup-ios.sh` が当てる（既存が大きければ下げない）
- **AI業務マネージャーに依頼2件を実装**（詳細は `chatwork-ai-manager/SESSION_LOG.md`）
  - 添付ファイル（Excel等）を読めるようにした。**添付を扱うコードが1行も無かった**のが原因
  - LINEから常駐を再起動できるようにした（「再起動」「全部再起動」「状態」）
  - 常駐4サービスを再起動し、新コードで稼働中
- **機密の受け渡しを整えた**
  - `keyline/data`（鍵の台帳・借主・免許証画像）を `secrets-manifest.txt` に追加し、
    メインPCから **書き出し済み**（`Dropbox-個人/apps-secrets-handoff/apps-secrets-usernoMac-mini.tar`・996KB）
  - `chatwork-ai-manager` は **一切運ばない**と明記（サブPCでは触らない・本人確認）

### 発生したエラーと解決策

- `secrets-sync.sh` が両PCとも同じ `apps-secrets.tar` へ書いていた → **双方向の受け渡しを同じ日に
  やると、先の書き出しを消す**。tar名にホスト名を入れ、import は「自分以外が書いた最新のtar」を選ぶよう修正
- 同スクリプトが SQLite を書きかけ（WAL）のまま固めていた → 固める前にチェックポイント。
  失敗しても `-wal` ごと運ぶので壊れない。作業用の `-shm` は同梱しない
- `visual-agent-check.sh` が「クリックできない」と誤診 → 真因は**前回実行で残った http.server が
  ポートを掴んだまま**で、消えた docroot を配って全404だったこと（pid取得が空振りしていた）。
  立てる前に pkill・pidを正しく取る・curlで中身を確かめてから操作、に修正
- `dev-setup.sh` を**実行中に編集**したため、走っていたプロセスが末尾で構文エラーを出した
  （導入自体は8本とも成功）。**動いているシェルスクリプトは編集しない**（bashが逐次読むため）

### 次回への引き継ぎ事項・未解決の課題

- **今夜サブPCで流す手順は `TODO.md` の先頭にまとめた**（pull → dev-setup → visual-agent-check →
  secrets import → secrets export → メモリ20本）
- 人の判断待ち3件は据え置き: Zenn残り1本→note / デジタル書斎のApp Store提出 / scrapmemoのビルド7提出
- KeyTag は**NFCタグ到着後の実機検証がまだ**。KeyLineの平文HTTP＋バックグラウンドタグ読み取りも未確認
- AI業務マネージャーの添付機能は、**実際にExcelを貼っての通し確認が未実施**（ローカル抽出までは確認済み）

## 2026-08-18（メインPC）— サブPCの作業を受領し、共通Visual Agentを1つに統合した

### 完了したこと

- **2台の分岐を合流させた。** サブPC 22コミット と メインPC 27コミット（未pushだった
  KeyLine/KeyTag・chatwork開発エージェント・GIS 等）を merge。衝突は `CLAUDE.md` と `TODO.md` の2つ。
  - `CLAUDE.md`: **アプリ個別の補足は各 README へ**（サブPC案）を採用。ただし origin 側を
    そのまま採ると**KeyLineの記述が消える**（サブPCはKeyLineを知らない）ため、
    `keyline/README.md`（既にあり同内容を網羅）と `digital-shosai/HANDOFF-APPSTORE.md` への
    ポインタを追加してから採用した
  - `TODO.md`: 担当PC列つきの表（サブPC案）に統一し、keyline 行を残した
  - 念のため `backup-main-20260818` ブランチに合流前のHEADを退避してある
- **サブPCからの依頼を実施**: `.dev-role=main` / `ai-tools-lab` → `ai-tools-base` の実体移動と
  空フォルダ削除 / `dev-doctor.py --sync --fetch` / メモリ差分の受領（本文2本を取込、
  `project_restoration_calculator.md` は濃い `project_restoration_calc.md` に統合して削除、
  索引を更新）。Dropbox の受け渡し置き場は中身を確認してから削除
- **共通 Visual Agent を統合**（本題）。2台が別々に作った MCP版 と `./va.sh` を、
  **1つの仕組み・2つの入口**に整理した。詳細は `VISUAL_AGENT.md`
  - `visual_agent.py`: ブラウザを**入口Aと同じ Google Chrome**（`channel=chrome`）に。
    無いPCでは同梱Chromiumへ自動フォールバックし、そう表示する（黙って別物を見ない）
  - `visual_agent.py`: Playwright の探索を `VA_PYTHON` → `agent-platform/.venv` → `.va-venv`
    → `python3` に。**agent-platform 決め打ちをやめた**（あのアプリが無いPCで死ぬため）
  - `visual-agent-check.sh`: **両方の入口**を1回で点検（`--mcp` / `--va` で片方だけも可）
  - `VISUAL_AGENT.md` を唯一の説明書に。`CLAUDE.md` は 2,021字 → 950字のポインタに縮小
- **実測（メインPC・2026-08-18）**: 入口B は Chrome / Chromium / `VA_PYTHON` 明示の3経路で
  `goto → shot → check → console --errors` 成功。入口A は `claude -p` から
  「開く→押す→見出しの変化を読む」まで成功。`./visual-agent-check.sh` が全項目 ✅
- **chatwork-ai-manager の常駐4サービスを再起動**（画面8540 / worker / LINE 8530 / ngrok）。
  11:33:51 に worker の起動ログ、8540・8530 とも HTTP 200、ngrok 固定ドメインも復帰を確認

### 発生したエラーと解決策

- **`visual-agent-check.sh` が「クリックの結果を読み取れなかった」と出た** → 原因は
  **過去の実行で残った `python3 -m http.server 8897` が居座っていた**こと。
  元の書き方が `( cd $tmp && python3 … & echo $! > pid )` で **pid を取れておらず**
  後片付けが空振りしていた。残ったサーバーは docroot を消されているので**全部404**を返し、
  ボタンが無いページを掴んでいた（＝Visual Agent 側の不具合ではない）。
  → 立てる前に `pkill -f "http.server $PORT"`、pid を正しく取る、**立てた後に curl で
  中身を確かめてからブラウザを動かす**、の3点に直した
- （合流時）`git merge` の origin 側をそのまま採ると KeyLine の記述が消える件は上記のとおり対処

### 次回への引き継ぎ事項・未解決の課題

- **サブPCへ**: `git pull` → `./visual-agent-check.sh` だけで統合版が使える。
  **メモリの実体20本が未受領**（索引にはあるのに本文が無い）。一覧は `TODO.md` の先頭にある
- **人の判断待ち（外部に出る操作なので勝手に進めない）**: ①Zenn 残り1本 → note の公開
  ②デジタル書斎の App Store 提出（`digital-shosai/HANDOFF-APPSTORE.md`）
  ③scrapmemo-petapeta のビルド7を ASC で審査提出
- `dev-doctor.py --sync` の残り警告: 機密5件が未設定（`brain-dump/.env.local` /
  `pasha-calo/.env.local` / `ai-ticket-counter/.env` / `theta-viewer/server/ftp-config.json` /
  `kaitori-dm-maker/senders.json`）。サブPCの点検では「不足0件」と出ていたので**あちらには
  実体がありそうだが未確認**。次の受け渡しのときに1件ずつ確かめて運ぶ

## 2026-08-17（夜・サブPC）— 開発ループを明文化し、検証を実行できるようにした

「Agentic Workflow のガイドラインを入れたい」という相談を受け、**このリポジトリの実情に合わせて縮めて**導入した。

### 完了したこと
- **CLAUDE.md に「5. 完了の定義」「6. 自律で進めてよい範囲と、必ず聞くこと」「7. タスクの書き方」を追加**
  （約1,500字。今日46%削った分を食い潰さない範囲に収めた）
  - 完了条件＝要件充足／**検証の最低ラインの実行**／**画面の目視**／既存機能を壊していない／記録／`--sync`
  - 種別ごとの検証ライン: Streamlit＝smoke_test＋**127.0.0.1で起動しHTTP 200**＋目視 ／
    Next＝lint+build(+validate) ／静的＝Consoleエラー0件＋目視 ／iOS＝`ios-build-guard.sh`
  - **自律の範囲はローカル完結のみ。** 外部へ出る操作（Chatwork/LINE返信・メール送信・FTP公開・
    Vercel本番・Zenn/note投稿・App Store提出）、戻せない操作、個人情報、**解釈が分かれる判断**は人に聞く
- **`./dev-doctor.py --verify <アプリ>` を追加**。上の最低ラインを実際に回す。
  `run.sh` を使わず **127.0.0.1 を明示**して立てる（不動産カテゴリの run.sh は 0.0.0.0）。
  `chatwork-ai-manager` と `mail-merge-pro` は**外部に送るので自動検証しない**（理由を出して飛ばす）
- **実測**: `business-plan-generator` → smoke_test ✓（総事業費25,501万・Excel 9,380バイト）＋
  127.0.0.1:8990 で **HTTP 200** ✓ ／ `ai-tools-base` → `validate` ✓ `lint` ✓
  （validateの⚠️は既知の「転載がまだ」5件と review 未記入4件のみ）

### 判断したこと（採用しなかった部分と理由）
- **`docs/tasks.md` `architecture.md` `decisions.md` `issues.md` の新設は採らなかった。**
  既存の「直下TODO.md（51本の索引）＋各アプリの TODO / SESSION_LOG / README」と二重になり、
  51アプリのタスクを1ファイルに集めると破綻する。→ tasks=各アプリTODO / decisions=README /
  issues=SESSION_LOGの未解決節 に**写像**した。`architecture` だけ不足なので、構成が複雑な3本
  （agent-platform / chatwork-ai-manager / building-manager）のREADMEに図を足す方針だけ決めた（未実施）
- **Task ID・9項目テンプレを全タスクに課すのも採らなかった。** 51本×全タスクでは続かない。
  複数セッションまたぎ・複数ファイル・外部影響のある改修だけ様式化する
- **「テスト成功」を無条件のDONE条件にしなかった。** 実測で pytest 0件・smoke_test 4本・
  npm test 2本しか無く、形式的なチェックになる。代わりに種別ごとの最低ラインを定義した

### 次回への引き継ぎ事項・未解決の課題
- 構成図（architecture）を3本のREADMEに追加するのは**未実施**
- 検証ラインを**全51本で通したわけではない**（2本で確認しただけ）。触るアプリで順次
- `--verify` は Next の `build` を既定で飛ばす（Intel Macで数分かかるため）。`--build` で回る

---

## 2026-08-17（夜・サブPC）— 2台のPCで同じ開発環境にするための整備（調査→修正→統合）

**目的**: 今回のような引き継ぎミス（コミット漏れ・改名の枝分かれ・MCPの取りこぼし）を、
「気をつける」ではなく**仕組みで検知する**状態にする。Build/Test の実走はご本人の判断で今回は省略。

### 完了したこと

**調査（変更なし・read-onlyのみ）**
- macOS 15.7.7 / **Intel x86_64** / Python **3.9.6（`/usr/bin/python3` のみ）** / Node **v26.3.1** /
  npm 11.16.0 / git 2.39.5 / **Docker は無し（リポジトリにも Dockerfile 0件＝不要）** / claude 2.1.233
- Git: `main` = `origin/main`（差分0）、tracked クリーン。**ローカルにしか無いもの**を発見:
  `stash@{0} pre-origin-sync` ／ ローカルブランチ `pre-sync-backup-20260626`・`pr-cyborg` ／
  `gh-pages` が27コミット遅れ。**いずれも触っていない**
- 依存: requirements.txt 31本 → venv 30本（不足は `business-plan-generator` のみ）。
  package.json 14本は全部 node_modules と lock あり。**バージョン固定ファイルが1つも無かった**
- 機密: `secrets-manifest.txt` 18件中17件あり。不足は `digital-shosai/.env.local` のみで**両PCに無い**
- 自動起動: launchd ロード0本だが **plistが2本ディスクに残存＝再ログインで復活する状態**だった。
  cron なし・hooks なし・ログイン項目は Dropbox/GoogleDrive のみ

**① 不足の解消**
- `business-plan-generator` の `.venv` 作成（streamlit 1.50.0 ほか。import 確認済み）→ **31/31本**
- `.python-version`(3.9.6) / `.nvmrc`(26.3.1) を追加。**現状値の固定**（Python 3.9 はEOLだが、
  31本のvenvが3.9.6なので揃えることを優先。上げるなら31本の作り直しとセット）
- launchd 2本を `launchctl disable` で**恒久無効化**（`unload` だけでは再ログインで復活する）
- 手動起動のまま `*:8540` でLANに出ていた chatwork-ai-manager 管理画面を停止

**② 検知の仕組み（`dev-doctor.py --sync`）** — 新規ツールを作らず既存を拡張
- Git（未コミット・未追跡・stash・push漏れ・remote未取得・ローカルだけのブランチ）
- **ignoreされていて git に入っていないソース候補**の検出 ← 2026-08-16の事故の真因を機械化
- `.python-version` / `.nvmrc` と実際の版の照合、機密の在り無し（**値は出さない**）、
  launchd・cron・**アプリのポート範囲だけの**LAN公開チェック
- WARNING を並べるだけで、commit・pull・install は一切しない

**④ ドキュメントの共通化**
- CLAUDE.md **27,288字 → 14,700字（46%削減）**。アプリ個別 12,999字を10本のREADMEへ移動
- SESSION_LOG の見出しに **PC名を必須化**（同日衝突の再発防止）、TODO に**担当PC列**
- SETUP.md に「**同じ環境**の定義表」（コード＋版＋lock＋機密＋常駐の5点）を明記
- `secrets-manifest.txt` に**リポジトリ外のPC側設定**（`~/.claude.json` の mcpServers 等）を注記

### 発生したエラーと解決策
- **症状**: `--sync` が「LANに公開されている待受」として `*:7000` `*:17500` などを警告した。
  **原因**: macOS(AirPlay) と Dropbox 自身の待受を拾っていた。
  **直し方**: 判定を**このリポジトリのポート範囲**（3000番台 / 5175 / 8500〜8620）に限定。
- **症状**（訂正）: TODO に「`photo-inpainter/` はフォルダごと無視されREADMEが他PCへ渡らない」とあった。
  **実測すると `!photo-inpainter/**` の許可行が既にあり、渡る**。古い情報だったのでTODOを訂正した。

### 次回への引き継ぎ事項・未解決の課題
- **Build/Test の実走は未実施**（ご本人の判断で①②④のみ実行）。したがって
  「ビルドとテストが通る」ことは**未確認**。確認するときは、外部に出るアプリ
  （chatwork-ai-manager / mail-merge-pro / flyer-creator・theta-viewer のFTP / ai-tools-base のVercel /
  building-manager の prisma db push）を**除外**し、Streamlit は `run.sh` を使わず
  `--server.address 127.0.0.1` を明示して起動すること（`run.sh` は不動産カテゴリだと 0.0.0.0）
- **メインPCの未コミット変更は、このPCからは確認できない**（見えるのは `origin/main` まで）。
  メインPC側で最初にやることは `git pull` と `./dev-doctor.py --sync`
- `VISUAL_AGENT`（MCP）は未受領。`claude mcp get VISUAL_AGENT` の出力待ち
- `stash@{0}` とローカルブランチ2本、`gh-pages` の27遅れは**そのまま**。中身の判断はご本人待ち

---

## 2026-08-17（夜・サブPC）— Claude Code に「目」を持たせた（Visual Agent）

### 完了したこと
- **`./va.sh`（`visual_agent.py`）を追加。** Claude Code 自身がブラウザを起動して見て操作し、
  UIを検証できるようにした。できること: 起動/終了・URL遷移・クリック・フォーム入力・
  キー操作（モーダルを Escape で閉じる等）・スクロール・ビューポート変更・
  スクリーンショット（表示部分／ページ全体）・DOM要約・アクセシビリティツリー・
  表示テキスト・Console・Network（ステータスと所要ms）・レスポンシブ3幅・
  UI崩れの機械検出（`check`）・`eval` での計測
- **`./see.sh`（`see.py`）も追加。** ブラウザ以外を見る用: Macの画面ぜんぶ（`screen`）と
  pptx/pdf/docx の見た目（`file`。QuickLook経由・1ページ目のみ）
- 実測: 公開サイト（ai-tools-base）で通し確認。撮影1.5MB/1440幅、Network 26件を捕捉、
  Console は log/error/**pageerror（未定義関数の呼び出し）**まで捕捉、
  クリックでページ遷移（`/` → `/tools`）まで確認
- **見つけた実際のUI崩れ（390px幅）**: 比較表が `div.table-scroll`（`overflow-x:auto`）の中で
  **表の幅832px に対し表示幅348px＝484px が隠れている**。横スクロールはできるが
  そう見える手がかりが無く、料金列が「$10/月〜（学生・OSS開発者は無」で切れて読めない。
  ヘッダーのロゴも2行に折れている（「AIツールベー/ス」）。**未修正**

### 発生したエラーと解決策
- **症状**: Console と Network が0件しか記録されない（ページは正しく開けている）。
  **原因**: 常駐プロセスの待ちに `time.sleep()` を使っていた。**Playwright の sync API は
  Playwright の呼び出し中しかイベントを配送しない**ため、素のsleepで待つと
  `page.on("console")` などが一切発火しない。
  **直し方**: 待ちを `page.wait_for_timeout(300)` に変えた（例外時のみ素のsleepへ退避）。
  → 直後に 26件のNetworkと3件のConsoleを捕捉。**同じ作りをするときはここを踏む**
- **症状**: `data:text/html,...` を渡すと `http://data:text/html,...` に化けて開けない。
  **原因**: URL省略形の補完を「`://` を含むか」で判定していた。
  **直し方**: `^[a-z][a-z0-9+.-]*:` でスキームの有無を見るようにした。
- **症状**: Console のログが文字化け（`ç›®ã®...`）。
  **原因**: テスト用 `data:` URLに charset を書いていなかったためブラウザ側でShift系解釈。
  **道具側は UTF-8 で正しい**（`;charset=utf-8` を付けたら「日本語ログの確認」と正常表示）。

### 次回への引き継ぎ事項・未解決の課題
- 上のUI崩れ（モバイルの比較表・ロゴの折れ）は**まだ直していない**。直す場所は
  `ai-tools-base/src`（表のラッパに横スクロールの手がかりを出す／狭い幅ではカード表示に切替）
- **`VISUAL_AGENT` というMCPサーバーは公開のものとして確認できなかった**（検索でも該当なし）。
  メインPCに 2026-08-17 に追加したとのことだが、こちらには設定も実体も来ていない。
  `claude mcp get VISUAL_AGENT` の出力がもらえれば同じものを入れる。
  それまでは上記 `./va.sh` が同じ役割を果たす（Playwright + Chromium・ローカル完結）
- ログイン済みの実ブラウザを見たい場合は **Chrome拡張（Claude in Chrome）** が要る。
  このPCでは拡張は入っているが**未接続**（`list_connected_browsers` が空）。人が Connect を押す必要がある

---

## 2026-08-17（夜・サブPC）— メインPCからの引き継ぎを受領し、改名の枝分かれを統合

### 完了したこと
- **メインPCの30コミットを取り込み、サブPCの4コミットとマージ**（`954844d`）。
  両PCが同じ日に「AIツールラボ→AIツールベース」の改名を別々にやっていたため、
  **フォルダ名を `ai-tools-base` に統一**（サブPC側を採用・ご本人の判断）。
  メインPC側の中身（`publish.sh`・3媒体の更新手順・公開サイトの索引・PCの役割分担）は全部取り込んだ
- **整備ツール5本を git に載せ直した**（`9935f9d`。`SETUP.md` / `dev-doctor.py` / `dev-setup.sh` /
  `secrets-sync.sh` / `secrets-manifest.txt` ＝ **575行が実体として入ったことを `git show --stat` で確認**）
- push 済み（`80ee5e9..9935f9d`）。Zenn は GitHub 連携なので、これで公開済み5本のリンクも新URLに直る
- **鍵・データ一式を受領**（`handoff-20260817` 31.6MB・101ファイルを `rsync --ignore-existing`）。
  `./dev-doctor.py` → **依存の作成が必要 0本 / 機密が足りないのは digital-shosai だけ**
  （それはメインPCにも実体が無いので取り下げ済み）
- **Claudeの記憶を受領**（59ファイル）。索引 `MEMORY.md` は**上書きせずマージ**した（22行追加）。
  重複していた古い記憶2本を整理（`project_app_catalog`=36本の古い一覧 → `app_list_master`=51本に統合、
  `project_restoration_calculator` → 詳しい `project_restoration_calc` に統合）。退避は `~/memory-backup`
- **Dropboxの受け渡し置き場を2つとも削除**（`handoff-20260817` 31.6MB ／ `pokecard-dex-handoff` 3.8GB）。
  消す前に確認: 鍵・データは上記のとおり着弾、`pokecard-dex/data` は 4.3GB・81,120ファイルで在る
- **サブPCの launchd 常駐を0本にした**（file-finder 8520 / owner-payout-tracker 8519 を unload）。
  8519/8520 の待受なし・`launchctl list | grep shinsei` が空。個人情報を含む画面の二重LAN公開も解消
- quote-generator（別リポジトリ）を `git pull` で最新化（`run.sh` が増えた）。`data/issuers.csv` も在る

### 発生したエラーと解決策
- **症状**: `git pull` が改名で衝突（`CONFLICT (file location): ai-tools-lab/publish.sh added in
  origin/main inside a directory that was renamed in HEAD`）ほか6ファイルが競合。
  **原因**: 同じ改名を2台で別々にコミットしたため（サブPCは**フォルダごと** `git mv`、
  メインPCは**中身だけ**書き換えてフォルダ名は据え置き）。**捨てて解決してはいけない**
  ケースだった（メインPC側だけに `publish.sh` と3媒体の手順があり、サブPC側だけに
  Search Console 移行と note リンク修正のログがあった）。
  **直し方**: 各ファイルを見比べて手で統合。`publish.sh` は `git add ai-tools-base/publish.sh` で
  新パスへ置き、`ai-tools-lab` の残り参照（`dev-doctor.py` のアプリ一覧・CLAUDE.md の表・
  公開サイトの節）を新名へ直した。**過去ログの旧名はそのまま残す**（当時の事実なので）

### 次回への引き継ぎ事項・未解決の課題
- **メインPCで1回だけ手作業が要る**（TODO の横断作業に記載）。`git pull` 後、gitに入らない実体を
  `ai-tools-lab/` → `ai-tools-base/` へ手で移す（`node_modules` / `.next` / `.vercel` / `.env*`）。
  Vercel のプロジェクト名は既に `ai-tools-base` なので、これで名前が全部揃う
- Zenn の未反映3本の出し直しと note の公開は**メインPCの担当**（ブラウザのログイン状態がある）
- `baikai-generator/.streamlit/secrets.toml` は両PCに無い。`dev-doctor.py` は「不要」と判定
  （このアプリは `claude` CLI を使いAPIキー不要）。**必要になったら作る**という理解で未確認
- 8540（chatwork-ai-manager の管理画面）はサブPCで手動起動のまま稼働中。役割分担の表で
  「サブPCは画面8540のみ可」なので止めていないが、**`*:8540` でLANに出ている**点は認識しておく

---

## 2026-08-17 — サブPC（2026-08-16）の作業をメインPCで受領

### 完了したこと
- **ai-tools-lab をメインPCで動く状態にした**（`HANDOFF.md` §1）。`npm install` 完了、
  `npm run validate` 通過（警告は既知の「転載がまだ」5件と review 未記入4件のみ）
- **機密の受け渡しを手動で代替**。`Dropbox-個人/handoff-20260817/` に
  `psa-collection/data/{orders,albums}.json` と `引き継ぎ-先に読む.txt` を配置
- 直下 `.gitignore` に許可行を追加（`HANDOFF.md` / `SETUP.md` / `dev-doctor.py` /
  `dev-setup.sh` / `secrets-sync.sh` / `secrets-manifest.txt`）
- **メインPCの 8526 / 8527 のLAN公開を解消**（下記）
- **agent-platform（マルチプロダクション・8532）を完成扱いにして正式に社内LAN共有へ**。
  もともと `.url` は配られ実際も `*:8532` で公開されていたが、`run.sh` は `127.0.0.1`・launchd未登録で、
  **手動起動のプロセスが残っているだけの状態**だった（＝再起動したら消える）。
  `run.sh` を `0.0.0.0` に直し、launchd `com.shinsei.agent-platform` に登録 → 疎通確認（LAN 200）。
  残件は作り込み（pptxの目視確認・字幕・投稿API等）で、通し実行はできる状態
- **business-plan-generator（事業計画案ジェネレーター）を社内LAN共有に載せた**（不動産31本目）。
  2026-07-28 に作られたまま展開されておらず、gitにも載っていなかった。動作は問題なし
  （`smoke_test.py` が総事業費25,501万・利回り実1.7/経費込4.0/単純6.6・Excel出力9,380バイトまで通り、
  画面も HTTP 200）。**port は README の 8527 が psa-collection と衝突していたため 8533 へ変更**。
  launchd `com.shinsei.business-plan-generator` 登録 → `192.168.1.105:8533` で疎通確認、
  Desktop の `.app`（→29本）と Dropbox共有フォルダの `.url`＋`icons/*.ico`（→22本）も設置
- **photo-inpainter（不動産写真AI・8506）をメインPCへ設置し、社内LAN共有に載せた**。
  サブPCで完成（2026-08-10）していたがメインPCには環境が無く、8506は待受なしだった。
  `.venv` 作成 → launchd `com.shinsei.photo-inpainter` 登録 → `192.168.1.105:8506` で疎通確認、
  Desktop の `.app`（27本→28本）と Dropbox共有フォルダの `.url`＋`icons/*.ico` も設置
- **個人Dropboxの受け渡し置き場を片付け**。受け取り済みを1件ずつ確認して削除:
  `handoff-20260815`（agent-platform の config/knowledge/.env・flyer-creator の .stats_key。
  5件ともメインPCに実体あり）／`chatwork-ai-manager-handoff` 165MB（サブPCが8/16にimport済み。
  必要なら `handoff_export.sh` で作り直せる）。残りは `handoff-20260817`(380KB) と
  `pokecard-dex-handoff`(3.7GB) で、**どちらもサブPCの受け取り確認後に消す**（今夜の手順③）
- CLAUDE.md に「**PCまたぎの受け渡し — 受け取ったら消す**」を作業ルールとして追加
- **今週サブPCで全アプリを触れるようにする準備**（依頼: 2026-08-17）。
  gitに入らない実体をメインPC全体から棚卸しし、`handoff-20260817/` に**リポジトリ直下と
  同じ形**で詰めた（合計31MB。`rsync --ignore-existing` 1回で復元できる形）。
  内訳＝鍵・設定10件（agent-platform/.env、building-manager/.env、flyer-creator/.stats_key、
  jyuusetsu-research・legal-crosscheck・realestate-valuation の secrets.toml、
  madori-tracer の .env.local と .secret_key、shorui-mobile/.env.local、theta-viewer/.env.local）
  ＋データ6アプリ（flyer-creator 29M / file-finder 1.5M / tsuikyaku-crm / shorui-cabinet /
  restoration-calculator / quote-generator）。
  **入れなかったもの**: psa-collection の画像443MB（サブPCで再取得できる）、
  pokecard-dex 4.3GB（別tarで受け渡し済み）、chatwork-ai-manager（専用スクリプトが正）

- **メインPCから3媒体（本体サイト / Zenn / note）を更新できるようにした**。
  入口は `ai-tools-base/publish.sh`（status / site / zenn / note）。
  ※当時のパスは `ai-tools-lab/`。2026-08-17夜のマージでフォルダ名を `ai-tools-base` に統一した
  Chromeを新規インストール→Claude拡張を接続、note・Zenn・Vercel にログイン。
  `npx vercel link` でプロジェクト **brain-dump/ai-tools-base** に紐づけ、
  `./publish.sh site` で**実際に本番デプロイして確認**（dpl_Ass2Jj9… READY・別名も同IDを配信）
- **「AIツールラボ」→「AIツールベース」への改名**に追従（37ファイル）。公開URLは
  `ai-tools-base.vercel.app`。旧URLは意図的に削除されており、公開済み記事のリンクが
  404になっていたので差し替えた（Zennのデプロイ履歴で反映を確認）
- **区分に「公開サイト」を追加**（5つ・URL付き。一覧の最後）。アプリの本数には数えない
- **メモリ（Claudeの記憶）をサブPCへ渡す仕組み**を用意。公開リポジトリに置けないため
  `handoff-20260817/memory-from-main/`（59ファイル）＋ TODO に取り込み手順（②-b）

### 発生したエラーと解決策
- **症状**: TODOの「【明日いちばん最初】メインPCで `./secrets-sync.sh export`」が実行できない。
  メインPCに `secrets-sync.sh` が無い。
  **原因**: 2026-08-16 にサブPCで作った整備ツール5本
  （`secrets-sync.sh` / `secrets-manifest.txt` / `dev-doctor.py` / `dev-setup.sh` / `SETUP.md`）は
  **コミットされていなかった**。コミットメッセージには書かれているが、
  `git show --stat` の中身は `.gitignore` と requirements の修正だけ。
  直下 `.gitignore` は**1行目から `*` で全部無視し、`!` で個別に許可する方式**なので、
  許可行の無い新規ファイルは `git add` しても入らない（`git add` はエラーを出さない）。
  **直し方**: メインPCで許可行を追加して push。サブPCで `git pull` 後に5本を `git add`→push。
  → 教訓: **直下に新規ファイルを置いたら `git status` ではなく
  `git show --stat <コミット>` で実体が入ったかを見る**（`git check-ignore -v <file>` で確認できる）。
- **症状**: サブPCからの依頼3件のうち `digital-shosai/.env.local` が用意できない。
  **原因**: メインPCにも存在しない（`.env.local.example` のみ）。運ぶ元が無い＝要件取り下げ。
- **症状**: photo-inpainter の依存を Python 3.12 の venv に入れようとすると
  `Failed building wheel for Pillow` で必ず落ちる。
  **原因**: `iopaint==1.6.0` が **`Pillow==9.5.0` をハード固定**しており、
  Pillow 9.5.0 には cp312 のホイールが無い（arm64は cp38〜cp311 まで）。
  pip はホイールが無いのでソースビルドへ落ち、ビルド環境が無いため失敗する。
  **直し方**: venv を `/usr/bin/python3`（3.9.6）で作り直す → 全依存が入り稼働。
  → 教訓: 「Pillowのビルド失敗」は**Python が新しすぎる**サイン。requirements の直接指定
  （`Pillow>=9.0.0`）ではなく、**依存の依存が固定していないか**を見る。
- **症状**: メインPCで **8527 psa-collection（保有明細・資産額）と 8526 kaitori-dm-maker が
  `*`（LAN全公開）で待ち受けていた**。どちらもツール分類で 127.0.0.1 が正。
  **原因**: `run.sh` は 127.0.0.1 に修正済みだったが、**動いているプロセスが 8/8 05:52 起動のまま**で
  修正前の設定を保持していた。**ファイルを直しても launchd の常駐プロセスは入れ替わらない。**
  **直し方**: `launchctl kickstart -k gui/$(id -u)/com.shinsei.<label>` で再起動
  → `lsof -nP -iTCP:<port> -sTCP:LISTEN` が `127.0.0.1:<port>` になり、HTTP 200 も確認。
  → 教訓: **バインド先を直したら `run.sh` の修正だけで終わらせず、必ず kickstart して lsof で見る。**

### 次回への引き継ぎ事項・未解決の課題
- サブPCで `git pull` → 整備ツール5本をコミットし直す（上記）
- **【今夜 19:56以降・メインPCで】Zenn の未反映3本を出し直す**
  （`./publish.sh zenn` → `./publish.sh status`）。そのあと note。Vercelのリンクとデプロイは完了済み
- サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）は**止める方針で確定**（今夜の手順④）
- **メインPCで残っているバインド違反1件**（未対応）: `3002` brain-dump（ツール／Next.jsの既定が 0.0.0.0。
  `run.sh` に `-H 127.0.0.1` を足す）。8532 agent-platform は完成扱いにしたので 0.0.0.0 のままで正しい
- ~~メインPCの未コミット19ファイル~~ → **アプリ単位で5コミットに分けて push 済み**（2026-08-17）。
  quote-generator は別リポジトリで、未コミットに見えた529行は**すでにpush済みの内容**だった
  （作業コピーが2コミット遅れていただけ。fast-forwardで解消し、`run.sh` だけ追加）
- **business-plan-generator の中身が会長の様式に合っているかは未検証**。計算とExcel出力は通るが、
  実データ1件での目視確認をしていない
- **社内への配り方を整理**（4本足りないように見えた件の決着）。
  横断ファイル検索(8520)・業務マニュアル(8521) は**`社内ツール/` の1つ上**（`（★必読★）新共有フォルダ/` 直下）に
  既に置いてあった＝毎日使う入口なので浅い位置。駐車場配置図ビューア(8522) は今回追加（`.url`＋`.ico`。
  `.ico` は Desktop の `.app` の `AppIcon.icns` を sips→PIL で変換し見た目を統一）。
  **AI業務マネージャー(8540) はオーナー管理の情報を扱うため配らない**（画面は 0.0.0.0＋パスワードのまま）
- **鍵が6本、メインPCに存在しない**（`brain-dump/.env.local` / `pasha-calo/.env.local` /
  `digital-shosai/.env.local` / `baikai-generator/.streamlit/secrets.toml` /
  `theta-viewer/server/ftp-config.json` / `kaitori-dm-maker/senders.json`）。
  CLAUDE.md は「brain-dump と pasha-calo に Geminiキーがある」と書いているが**メインPCには無い**。
  サブPC側にあるかを今夜確認する（両方に無ければ作り直しが要る＝その6本は今どちらでも動かない）
- CLAUDE.md のスリム化（メインPCで実施予定）も**未着手のまま**

## 2026-08-16 — サブPCで全アプリを触れるようにする（横断整備）

### 完了したこと
- **道具を3つ追加**（リポジトリ直下）
  - `dev-doctor.py` … 全51本の「依存／機密／待受／稼働」を1画面で表示。
    ツール・ゲーム分類が `0.0.0.0` で待ち受けていたら ⚠️、
    chatwork-ai-manager の**本体**（worker / LINE webhook / ngrok）がこのPCで
    動いていたら ⚠️（管理画面8540は動かしてよい）
  - `dev-setup.sh` … 不足している `.venv` / `node_modules` を一括作成。
    **venvは python3.11 を優先**（システムの3.9では入らない依存がある）。
    chatwork-ai-manager だけ venv を作らない（claude 呼び出しが SIGSEGV になるため）
  - `secrets-sync.sh` ＋ `secrets-manifest.txt` … 機密を**個人Dropbox**経由で運ぶ。
    `check` / `export` / `import`。対象はパスだけを列挙し、値は書かない
- **依存を21本ぶん作成**（Python 16 / Node 5）→ 不足0本。ディスクは 40GB → 34GB
- `.gitignore` を**まとめて除外する形**に変更（`**/.venv/` 等）。
  従来はアプリごとの個別指定で、**新規作成の .venv が2本 git に載りかけていた**
- `SETUP.md` を新規作成（手順・PCまたぎの注意・見つかった不具合）

### 発生したエラーと解決策
**依存を作り直したことで、実際の不具合が4件出た。3件は同じ形。**

- `madori-tracer` … `pip install -r requirements.txt` が必ず失敗。
  原因は `streamlit-cropper>=0.7` を要求しているが**PyPIには 0.3.1 までしか無い**。
  実在する版へ修正 → `st_cropper` の import まで確認
- `payment-reconciler` … 入金の突合率が下がるがエラーは出ない。
  原因は `pykakasi`（漢字→カナ変換）が try/except の暗黙フォールバックで、
  `requirements.txt` に入っていなかった。requirements に追加＋**未導入なら画面に警告**
- `kaitori-dm-maker` … 謄本PDF取込だけ動かない。原因は借りている
  `baikai-generator/services/registry_parser.py` の依存（pdfplumber / pymupdf）が未宣言
- `realestate-valuation` / `restoration-calculator` / `settlement-creator` …
  requirements に `pymupdf>=1.24.0` と書いてあるのに**venvに入っていなかった**。
  `pdf_orient.py` は `except ImportError: return -1` なので、
  **PDFの向き補正が黙ってスキップ**されていた。入れ直して解消

→ 4件中3件が **photo-inpainter と同じ「入れ忘れた依存が静かに代替経路へ落ちる」形**。
  optional import を書くときは、落ちたことが見えるようにすること。

**道具側の不具合も2つ潰した**
- `dev-setup.sh` が `$log（末尾:…` で落ちた。bashは**変数名の直後の全角文字を名前の一部と解釈する**
  ことがある → `${log}` と括る
- `dev-doctor.py` が chatwork の本体を誤検知。`ps` の全文検索だと**検査コマンド自身の
  文字列**を拾う（スクリプトに "run_worker.sh" と書いてあるため）→ ポートとプロセス名で判定

### 次回への引き継ぎ事項・未解決の課題
- **メインPCで `./secrets-sync.sh export` を実行してもらう。** サブPCに無いのは3件:
  `digital-shosai/.env.local` / `psa-collection/data/orders.json` / `psa-collection/data/albums.json`
  （受け取ったらサブPCで `./secrets-sync.sh import`）
- **launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）がサブPCでも
  LAN公開で動いている。** メインPCと二重公開で、どちらも個人情報を含む。止めるかは未判断
  （止めるなら `launchctl unload ~/Library/LaunchAgents/com.shinsei.<アプリ>.plist`）
- 既存の venv のうち14本は Python 3.9 のまま（動いてはいる）。
  3.10以上を要求する依存が来たら `rm -rf <app>/.venv && ./dev-setup.sh <app>` で作り直す


## 2026-08-16 — メインPC → サブPC の引き継ぎ受領（chatwork-ai-manager）

### 完了したこと
- サブPCで `git pull origin main`（5コミット）。メインPCで作られた **chatwork-ai-manager
  （AI業務マネージャー・新規48本目→49本目）** 一式と flyer-creator の更新を取得
- `chatwork-ai-manager/handoff_import.sh` で Dropbox-個人の機密tar(172MB)を展開
  （secrets / DB / 内部docs / ngrok authtoken）。詳細はアプリ側 `SESSION_LOG.md` に記載
- **常駐サービスはメインPCに置いたまま、サブPCは管理画面(8540)のみ起動**して疎通確認（HTTP 200）

### 発生したエラーと解決策
- なし

### 次回への引き継ぎ事項・未解決の課題
- **worker / LINE webhook / ngrok は「1台のPCでのみ」動かす決まり**（二重返信＋ngrok固定ドメインの
  取り合いが起きる）。移す場合は先にメインPCで `launchctl unload …chatwork-ai-manager*.plist`
- **DBは双方向マージできない**ので、常駐を移す直前に必ず export→import で最新へ揃える
- CLAUDE.md のスリム化（横断作業）は**まだ未着手**。メインPCで実施予定のまま

## 2026-08-15（深夜〜08-16）— メインPCへの引き継ぎと、アプリ一覧の棚卸し

### 完了したこと

**引き継ぎ（gitに載っていなかったものを解消）**
- `agent-platform`（マルチプロダクション）… 74ファイルを追加。**丸ごと未コミットだった**
- `kato-flyer` → `flyer-creator`（チラシクリエーター）… 19ファイルを追加。**1ファイルも入っていなかった**
- Dropbox（個人）`handoff-20260815/` に、gitに入れられない小物**192KB**を配置。
  `.env`（実キー）／`config/company.json`／`knowledge/`／`.stats_key` ＋ 手順書。
  当初メール添付のつもりでキーを伏せた zip を作ったが、**Dropbox なら伏せる必要がない**ので作り直した
- ポケモンカード図鑑は 2026-08-14 に Dropbox 配置済み（`pokecard-dex-handoff/` 4.0GB）で対応不要と確認
- `quote-generator` は**独立したGitHubリポジトリ**（shinsei99/quote-generator）で同期済みと判明。
  ホームのリポジトリに無いのはそのため。作業不要

**コミット前に見つけて直した秘密情報**
- `flyer-creator/tracking.py` に集計ページの閲覧キーが直書き、さらに `HANDOFF.md` にも
  URL付きで書かれていた → `.stats_key`（gitignore）へ移し、両方から値を削除。
  **公開リポジトリなので、コミット前の走査は必ずやること**
- `agent-platform/.env` の Gemini・Pexels キーは gitignore 済みで混入なしを確認

**アプリ一覧の棚卸し（CLAUDE.md）**
- 本数の記載が実態とズレていた（記載45本 → 実際48本）。見出しと表の行数を一致させた
- `photo-search`（1.3GB）… 一覧にもgitにも無い幽霊アプリだった。**不要のため削除**（ゴミ箱へ）。
  写真の原本は Dropbox、フォルダ内は派生物のみ。`data/people.json`（顔への名前付け）だけは
  作り直せないので、ゴミ箱を空にする前に要否を判断すること
- `pdf-organizer` … `shorui-cabinet` の「📄 PDFを整理」タブに**統合済み**だったので一覧から削除。
  知見（sonnet/opus の使い分け・ウィンドウ30/8ページ・`_fill_gaps`・和暦変換）は
  **統合先の実装に同じものがあることを確認してから**書類キャビネットの節へ移した
- `agent-platform` を **ツール → 不動産**へ変更。ただし開発中なので `run.sh` は `127.0.0.1` のまま。
  社内LAN共有は「不動産の**完成済み**のみ」の決まりのため、完成時に `0.0.0.0`＋launchd登録
- App Store 状況を更新（水泳記録トラッカー＝配信済み、スクラップメモ＝1.0.2 build6 配信済み）。
  配信済みは6本、審査中はにゃんこのアイス屋さん1本

**.gitignore（「`*` で全無視＋`!` で許可」方式）に追加した除外**
- `agent-platform/.cache/`（見本画像）・moviepy の一時mp4・`.DS_Store`
- `flyer-creator/` 一式（`.venv` / `data/` / `site/` / `.stats_key` / 旧免許番号入りロゴ）

### 発生したエラーと解決策

- **フォルダを改名すると `.venv` が動かなくなる**（`kato-flyer` → `flyer-creator`）。
  venv は作成時のパスを `bin/*` の shebang と `pyvenv.cfg` に焼き込むため。
  → 14箇所を sed で書き換えて復旧（作り直し不要）。**改名時は必ず確認すること**
- **別プロセスで描画するアプリに相対パスを渡すと、相手の作業フォルダに書き出される**。
  `flyer-creator/engine.py` が `agent-platform` を cwd にして描くため、出力が向こうへ消えた。
  → `Path(out_dir).resolve()` で絶対パス化
- **PowerPointの .pptx を機械で画像化できない**（未解決）。LibreOffice未導入、
  `pdftoppm`/`gs`/`mutool` も無し、PowerPointのAppleScript書き出しは "ok" を返すのに
  ファイルが生成されない。**原因未特定**。`.venv` に `pypdfium2` はあるのでPDFさえ作れれば
  PNG化はできる。マルチプロダクションのスライド目視確認が止まっている原因

### 次回への引き継ぎ事項・未解決の課題

- **メインPC側にしか無いものがある**: `pdf-organizer`（統合済みなので不要）のほか、
  メインPC → こちらの共有は確認していない。逆方向の棚卸しは未実施
- CLAUDE.md のスリム化（19,159字・うち55%がアプリ個別の補足）は**メインPCで実施予定**。
  手順は直下 `TODO.md` の横断作業に記載
- マルチプロダクションを社内LANへ出すときは、`run.sh` を `0.0.0.0` に変えて launchd 登録し、
  CLAUDE.md の「バインド先のルール」の表も直す
