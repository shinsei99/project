# SESSION LOG — 横断作業

**1つのアプリで完結する作業のログはここに書かない。** それは
`<アプリ>/SESSION_LOG.md` に書く（例: `pokecard-dex/SESSION_LOG.md`）。

ここに書くのは、複数のアプリにまたがる作業だけ。
ポート割り当ての変更、launchd の整理、共通モジュール（`pdf_orient.py` など）の変更、
`.gitignore` や公開方法の方針変更、といったもの。

新しい節は**このすぐ下に追記**する（上が新しい）。書式は `CLAUDE.md` の作業ルール参照。

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
- **個人Dropboxの受け渡し置き場を片付け**。受け取り済みを1件ずつ確認して削除:
  `handoff-20260815`（agent-platform の config/knowledge/.env・flyer-creator の .stats_key。
  5件ともメインPCに実体あり）／`chatwork-ai-manager-handoff` 165MB（サブPCが8/16にimport済み。
  必要なら `handoff_export.sh` で作り直せる）。残りは `handoff-20260817`(380KB) と
  `pokecard-dex-handoff`(3.7GB) で、**どちらもサブPCの受け取り確認後に消す**（今夜の手順③）
- CLAUDE.md に「**PCまたぎの受け渡し — 受け取ったら消す**」を作業ルールとして追加

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
- **症状**: メインPCで **8527 psa-collection（保有明細・資産額）と 8526 kaitori-dm-maker が
  `*`（LAN全公開）で待ち受けていた**。どちらもツール分類で 127.0.0.1 が正。
  **原因**: `run.sh` は 127.0.0.1 に修正済みだったが、**動いているプロセスが 8/8 05:52 起動のまま**で
  修正前の設定を保持していた。**ファイルを直しても launchd の常駐プロセスは入れ替わらない。**
  **直し方**: `launchctl kickstart -k gui/$(id -u)/com.shinsei.<label>` で再起動
  → `lsof -nP -iTCP:<port> -sTCP:LISTEN` が `127.0.0.1:<port>` になり、HTTP 200 も確認。
  → 教訓: **バインド先を直したら `run.sh` の修正だけで終わらせず、必ず kickstart して lsof で見る。**

### 次回への引き継ぎ事項・未解決の課題
- サブPCで `git pull` → 整備ツール5本をコミットし直す（上記）
- ai-tools-lab の残り: `npx vercel login` → `npx vercel link`（team: brain-dump / project: ai-tools-lab）。
  公開は Zenn の上限が解ける **8/17 19:56 以降**、`ai-tools-lab/drafts/PUBLISH.md` の順で1日2本
- サブPCの launchd 常駐2本（file-finder 8520 / owner-payout-tracker 8519）の二重LAN公開は**未判断のまま**
- **メインPCで残っているバインド違反2件**（未対応）: `3002` brain-dump（ツール／Next.jsの既定が 0.0.0.0）、
  `8532` agent-platform（開発中＝127.0.0.1が正。`run.sh` は正しいので手動起動と思われる）
- メインPCに**前からの未コミット作業**が19ファイル分ある（mail-merge-pro / realestate-valuation /
  restoration-calculator / parking-map / memorandum-generator の icon-src）。素性を確認してから整理する
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
