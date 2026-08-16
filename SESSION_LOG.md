# SESSION LOG — 横断作業

**1つのアプリで完結する作業のログはここに書かない。** それは
`<アプリ>/SESSION_LOG.md` に書く（例: `pokecard-dex/SESSION_LOG.md`）。

ここに書くのは、複数のアプリにまたがる作業だけ。
ポート割り当ての変更、launchd の整理、共通モジュール（`pdf_orient.py` など）の変更、
`.gitignore` や公開方法の方針変更、といったもの。

新しい節は**このすぐ下に追記**する（上が新しい）。書式は `CLAUDE.md` の作業ルール参照。

---

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
