# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## ★ 最優先事項 — 全アプリ一覧（2026-07-14時点）

**カテゴリ:** 不動産 / ツール / ゲーム の3分類（全38本）  
**社内LANルール:** 不動産カテゴリの完成済みのみ共有（launchd常時起動）

### 不動産（24本）

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

### ツール（8本）※社内LAN共有なし

| アプリ名 | フォルダ名 | port | 外部公開 |
|---|---|---|---|
| 送付書ジェネレーター | soufu-generator | 8518 | — |
| デジタル書斎 | digital-shosai | 3001 | — |
| ブレイン・ダンプ自動整理 | brain-dump | 3002 | Vercel（brain-dump-sable-one.vercel.app） |
| スクラップメモ + PetaPeta Clipper | scrapmemo-petapeta + petapeta-extension | — | GitHub Pages |
| 水泳記録トラッカー | swim-tracker-react | — | GitHub Pages |
| ママカウンター | mom-counter | — | GitHub Pages / App Store ✅ v1.0.1 |
| Mac一斉メール送信 | mail-merge-pro | — | Macアプリ |
| フォトリメイク | photo-remake | — | iOS App Store申請前 |

### ゲーム（6本）※社内LAN共有なし

| アプリ名 | フォルダ名 | 外部公開 |
|---|---|---|
| ひよこ防衛軍 | piyo-defense | GitHub Pages |
| カラー重力ゲーム | color-gravity | GitHub Pages |
| サイボーグ防衛軍 | cyborg-defense | GitHub Pages |
| にゃんこ大脱出 | neko-escape | GitHub Pages |
| にゃんこのアイス屋さん | nyanko-ice | iOS App Store申請中 |
| ネオンブロック | neon-blocks | iOS App Store申請予定（メインPCで作業） |

### 業務マニュアル（Web）補足 ※不動産カテゴリに計上

- **大京商事 業務マニュアル（Web）** … 自己完結HTML一枚（22マニュアル）。所在: `gyomu-manual/業務マニュアル.html`（2026-07-10作成）。生成スクリプト: `gyomu-manual/generate.py`（`python3 generate.py` で再生成可）。port無し・ブラウザで直接開く運用。

### parking-map（駐車場配置図ビューア）補足

- 第一号: 角屋(横堤)モータープール（全41区画）。`serve.py` が起動の度にレントロールxlsxを読み最新の空き状況を反映（port 8522）。車室レイアウトは`template.html`に固定、中身のみ動的差し込み。個人情報を含む静的版はgitignore対象。他物件（大京モータープール／本庄西／ベリエール等）は今後同方式で展開予定。launchd登録済み・社内LAN共有済み（2026-07-14、com.shinsei.parking-map、`serve.py --daemon`でブラウザ自動起動を抑制）。

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
| 8600 | AI受付＆起票カウンター | com.shinsei.ai-ticket-counter |

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
