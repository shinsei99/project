# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ★ 最優先事項 — 全アプリ一覧（2026-07-14時点）

**カテゴリ:** 不動産 / ツール / ゲーム の3分類（全41本）  
**社内LANルール:** 不動産カテゴリの完成済みのみ共有（launchd常時起動）

### 不動産（26本）

| アプリ名 | フォルダ名 | port | 社内LAN | 外部公開 |
|---|---|---|---|---|
| 手書き検針記録 | handwriting-ocr | — | 開発中 | — |
| 見積書自動生成ツール | quote-generator | 8503 | ✅ | — |
| 物件管理案内文ジェネレーター | property-notice-generator | 8504 | ✅ | — |
| マイソクコンバーター | maisoku-converter | 8505 | ✅ | — |
| 不動産写真AI | photo-inpainter | — | 開発中 | — |
| 原状回復費用自動精算 | restoration-calculator | 8508 | ✅ | — |
| AI不動産価格査定 | realestate-valuation | 8509 | ✅ | — |
| 決済案内書自動作成 | settlement-creator | 8510 | ✅ | — |
| 売買書類クロスチェック | legal-crosscheck | — | 開発中 | — |
| 間取り図トレーサー | madori-tracer | 8511 | ✅ | — |
| THETAパノラマ3D空間化 | theta-viewer | 8512 | ✅ | GitHub Pages |
| 特約条項ジェネレーター | tokuyaku-generator | 8513 | ✅ | — |
| 入金突合（消込）システム | payment-reconciler | 8514 | ✅ | — |
| 物件写真一括リサイズ | image-resizer | 8515 | ✅ | GitHub Pages |
| 顧客追客マネージャー | tsuikyaku-crm | 8516 | ✅ | — |
| AI重説調査〜Excel自動入力 | jyuusetsu-research | — | 開発中 | — |
| 媒介契約書ジェネレーター | baikai-generator | 8517 | ✅ | — |
| AI受付＆起票カウンター | ai-ticket-counter | 8600 | ✅ | — |
| マンション・ビル管理 | building-manager | — | 開発中 | — |
| オーナー送金・月次締めマネージャー | owner-payout-tracker | 8519 | ✅ | — |
| 横断ファイル検索ブラウザ | file-finder | 8520 | ✅ | — |
| 不動産・金融マスター電卓 | realestate-calc | 8507 | ✅ | GitHub Pages / App Store ✅ |
| 業務マニュアル（Web） | gyomu-manual | 8521 | ✅ | — |
| 駐車場配置図ビューア | parking-map | 8522 | ✅ | — |
| 覚書・合意書ジェネレーター | memorandum-generator | 8524 | ✅ | — |
| 送付書メーカー | soufu-maker | 8525 | ✅ | — |

### ツール（10本）※社内LAN共有なし

| アプリ名 | フォルダ名 | port | 外部公開 |
|---|---|---|---|
| 送付書ジェネレーター | soufu-generator | 8518 | — |
| デジタル書斎 | digital-shosai | 3001 | — |
| ブレイン・ダンプ自動整理 | brain-dump | 3002 | Vercel（brain-dump-sable-one.vercel.app） |
| スクラップメモ + PetaPeta Clipper | scrapmemo-petapeta + petapeta-extension | — | GitHub Pages / App Store申請中 |
| 水泳記録トラッカー | swim-tracker-react | — | GitHub Pages |
| ママカウンター | mom-counter | — | GitHub Pages / App Store ✅ v1.0.1 |
| Mac一斉メール送信 | mail-merge-pro | — | Macアプリ |
| フォトリメイク | photo-remake | — | iOS App Store配信済み ✅ |
| 買取DMジェネレーター | kaitori-dm-maker | 8526 | — |
| PSA保有カード管理 | psa-collection | 8527 | — |

### ゲーム（6本）※社内LAN共有なし

| アプリ名 | フォルダ名 | 外部公開 |
|---|---|---|
| ひよこ防衛軍 | piyo-defense | GitHub Pages |
| カラー重力ゲーム | color-gravity | GitHub Pages |
| サイボーグ防衛軍 | cyborg-defense | GitHub Pages |
| にゃんこ大脱出 | neko-escape | GitHub Pages |
| にゃんこのアイス屋さん | nyanko-ice | iOS App Store申請中 |
| ネオンブロック | neon-blocks | iOS App Store配信済み ✅ |

### 業務マニュアル（Web）補足 ※不動産カテゴリに計上

- **大京商事 業務マニュアル（Web）** … 自己完結HTML一枚（22マニュアル）。所在: `gyomu-manual/業務マニュアル.html`（2026-07-10作成）。生成スクリプト: `gyomu-manual/generate.py`（`python3 generate.py` で再生成可）。port無し・ブラウザで直接開く運用。

### parking-map（駐車場配置図ビューア）補足

- 第一号: 角屋(横堤)モータープール（全41区画）。`serve.py` が起動の度にレントロールxlsxを読み最新の空き状況を反映（port 8522）。車室レイアウトは`template.html`に固定、中身のみ動的差し込み。個人情報を含む静的版はgitignore対象。他物件（大京モータープール／本庄西／ベリエール等）は今後同方式で展開予定。launchd登録済み・社内LAN共有済み（2026-07-14、com.shinsei.parking-map、`serve.py --daemon`でブラウザ自動起動を抑制）。

### 買取DMジェネレーター（kaitori-dm-maker）補足 ※ツール・port 8526

- 所有者台帳（確定15列・1物件1行：`NO/市/所在/地番/地目/地積・㎡/建物種類/建物構造/床面積・㎡/登記名義人/持分/郵便番号/現住所/電話番号/備考`）から、未活用地・空き家の**買取DM（Word）を差し込み量産**。文面は「建物買取DM横書き_改良版」準拠（ネイビー見出し・4メリット・約40万円囲みボックス・新誠/大京署名切替）。Streamlit+python-docx。
- **謄本PDF取込**：サイドバー「台帳更新」から謄本を複数（5件程度）アップ→AI読取→台帳に行追加。読取は**同リポジトリの`baikai-generator/services/registry_parser.py`を再利用**（`claude` CLIビジョン、パスは`shutil.which`で解決）。市/所在の分離・地目/地積・建物種類/構造/床面積・登記名義人/現住所を自動抽出。「1ファイル=1物件」/「全ファイル=1物件に統合」を選択可。
- **差出人**はサイドバーで追加・編集・削除（`senders.json`に保存。無ければコード内`DEFAULT_SENDERS`から生成）。DM一覧は各行チェックで送付先選択（既定全選択）、結合docx/個別ZIP出力。
- `senders.json`は個人情報を含むため**gitignore**（公開リポジトリに出さない）。メインPCへはコード内`DEFAULT_SENDERS`が既定として引き継がれる。launchd未登録（ツール分類のため社内LAN共有なし）。

### PSA保有カード管理（psa-collection）補足 ※ツール・port 8527

- PSA「My Collection」エクスポートCSV（`data/collection.csv`）を読み、**保有カードの検索・絞り込み・保管場所記録**を行う在庫管理Streamlit。初回取込は871件（保有381 / 売却済490、PSA10=541、ほぼポケカ日本語版＋ワンピースTCG）。
- 保管場所・メモは`data/storage_notes.json`に**証明書番号キー**で別管理。CSVを丸ごと差し替えても消えない設計（サイドバー「データ更新」でアップロード差し替え）。一覧の`PSA`列は`psacard.com/cert/<番号>`へのリンク。
- **カード画像**（🖼ギャラリータブ）: PSA公開API `GET /publicapi/cert/GetImagesByCertNumber/<cert>`（`Authorization: bearer <token>`、トークンは psacard.com/publicapi で無料発行）から取得し`data/images/<cert>[_back].jpg`に**永久キャッシュ**。**無料枠1日100件**のため上限で自動停止→翌日続きから（381枚なら4日で完了）。当日カウントは`data/image_state.json`。DL失敗時は画像URLを`data/image_urls.json`に控えてブラウザ直リンク表示にフォールバック。手動アップロード（ファイル名＝証明書番号）にも対応。実装は`psa_images.py`。
- **psacard.comの証明書ページはCloudflareで403**。サーバー側スクレイピング不可なので画像の自動取得は公開API経由のみ（この結論は再調査不要）。
- `data/`は保有明細と資産額を含むため**gitignore**（公開リポジトリに出さない）。他PCではCSVを`data/collection.csv`に置いて起動。launchd未登録（ツール分類のため社内LAN共有なし）。
- 元データの制約: `My Cost`/`My Value`/`Date Acquired`/`Source`/`My Notes`はPSA側で全件空欄 → **仕入値ベースの利益は算出不可**（売却額−手数料=手取り まで）。`Year`に`1998-99`形式が4件混在するため先頭4桁を数値年として扱う。

### theta-viewer FTP APIサーバー port修正（2026-07-14）

- 旧: port 8519 → 新: **port 8523**。理由: 8519は`owner-payout-tracker`が既に使用しており実際は起動時にクラッシュしていた（KeepAliveで再起動ループ）。誰かが以前この衝突に気づき未コミットのまま8522に変更していたが、それはparking-map用に予約された番号と衝突するため、最終的に空きポート8523へ変更・再ビルド（`npm run build`→vite preview再起動）して確定。関連ファイル: `theta-viewer/server/server.js`（`const PORT`）、`theta-viewer/src/firebase.ts`（`API_BASE`）。

### 社内LAN常時起動ポート一覧（launchd / メインMac）

| port | アプリ名 | plist |
|---|---|---|
| 8503 | 見積書自動生成ツール | com.shinsei.quote-generator |
| 8504 | 物件管理案内文ジェネレーター | com.shinsei.property-notice-generator |
| 8505 | マイソクコンバーター | com.shinsei.maisoku-converter |
| 8507 | 不動産・金融マスター電卓 | com.shinsei.realestate-calc |
| 8508 | 原状回復費用自動精算 | com.shinsei.restoration-calculator |
| 8509 | AI不動産価格査定 | com.shinsei.realestate-valuation |
| 8510 | 決済案内書自動作成 | com.shinsei.settlement-creator |
| 8511 | 間取り図トレーサー | com.shinsei.madori-tracer |
| 8512 | THETAパノラマ3D空間化 | com.shinsei.theta-viewer |
| 8513 | 特約条項ジェネレーター | com.shinsei.tokuyaku-generator |
| 8514 | 入金突合（消込）システム | com.shinsei99.payment-reconciler |
| 8515 | 物件写真一括リサイズ | com.shinsei.image-resizer |
| 8516 | 顧客追客マネージャー | com.shinsei.tsuikyaku-crm |
| 8517 | 媒介契約書ジェネレーター | com.shinsei.baikai-generator |
| 8519 | オーナー送金・月次締めマネージャー | com.shinsei.owner-payout-tracker |
| 8520 | 横断ファイル検索ブラウザ | com.shinsei.file-finder |
| 8521 | 業務マニュアル（Web） | com.shinsei.gyomu-manual |
| 8522 | 駐車場配置図ビューア | com.shinsei.parking-map |
| 8523 | theta-viewer FTP APIサーバー（server.js） | com.shinsei.theta-viewer-api |
| 8524 | 覚書・合意書ジェネレーター | com.shinsei.memorandum-generator |
| 8525 | 送付書メーカー | com.shinsei.soufu-maker |
| 8526 | 買取DMジェネレーター（※ツール・localhost・社内共有なし／常時起動のみ） | com.shinsei.kaitori-dm-maker |
| 8600 | AI受付＆起票カウンター | com.shinsei.ai-ticket-counter |
| 5175 | 間取り図トレーサー 手動編集エディタ（editor/、Vite+React+TS） | com.shinsei.madori-tracer-editor |

---

## ★ iOS App Store 再配信ルール（再発防止・必読）

**修正版を再アップロードするときは、必ずビルド番号（`CURRENT_PROJECT_VERSION`）を +1 する。**

> 2026-07-22の事故：photo-remake / neon-blocks とも、修正版を **build 1 のまま** 再アーカイブしていた。App Store Connect は「build 1 は既存」で新ビルドを受け付けず、**古い（修正前の）build 1 がそのまま審査を通り配信**されていた。ユーザーには「直したはずの不具合が残っている」状態に見えた。→ 両アプリを **1.0.1 / build 2** に繰り上げて解決。

### 再配信チェックリスト（Archive前に必ず）

1. `CURRENT_PROJECT_VERSION`（ビルド番号）を **既存の全アーカイブより大きい値**に +1 する
   - ネイティブ: `<app>.xcodeproj/project.pbxproj`（Debug/Release両方）＋ `project.yml`（xcodegen運用時）
   - Capacitor: `ios/App/App.xcodeproj/project.pbxproj`（※`ios/`はgitignore。`cap sync`しても番号は保持されるが、`cap add ios`でやり直すと1に戻る）
2. 必要なら `MARKETING_VERSION`（表示バージョン）も上げる（例 1.0.0 → 1.0.1）
3. **衝突チェック**: `./ios-build-guard.sh <app-folder>` を実行し「衝突なし」を確認（`--bump`で自動+1も可）
4. Capacitorは `npx cap sync` を実行してからArchive（`.xcworkspace`を開く）
5. Archive → Upload → App Store Connectで **今上げたbuild番号** が選択肢に出ることを確認してから提出
6. 配信物のソースは必ずコミット＆push（修正が手元だけに残ると同じ事故が再発する）

---

## Environment

- OS: macOS (darwin x86_64)
- Shell: zsh
- Custom binaries in `~/.local/bin` (added to PATH via `~/.zshrc`):
  - `gh` — GitHub CLI v2.94.0
  - `claude` — Claude Code CLI

## GitHub

Authenticated as **shinsei99** via `gh auth login`. The remote repository is `https://github.com/shinsei99/project` (public). Static HTML apps are published via GitHub Pages from the `gh-pages` branch (root), one folder per app, served at `https://shinsei99.github.io/project/<app>/`.

Common `gh` commands used in this repo:

```bash
gh repo view          # Show repository info
gh pr create          # Create a pull request
gh issue list         # List issues
```

## Git

```bash
git add <file>
git commit -m "message"
git push origin main
```
