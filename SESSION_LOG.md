# SESSION LOG — 横断作業

**1つのアプリで完結する作業のログはここに書かない。** それは
`<アプリ>/SESSION_LOG.md` に書く（例: `pokecard-dex/SESSION_LOG.md`）。

ここに書くのは、複数のアプリにまたがる作業だけ。
ポート割り当ての変更、launchd の整理、共通モジュール（`pdf_orient.py` など）の変更、
`.gitignore` や公開方法の方針変更、といったもの。

新しい節は**このすぐ下に追記**する（上が新しい）。書式は `CLAUDE.md` の作業ルール参照。

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
