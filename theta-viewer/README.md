# THETAパノラマ3D空間化（theta-viewer）

RICOH THETA で撮った**全天球写真（エクイレクタングラー）をブラウザ内でAI解析し、
Three.js で「奥行きのある3D空間」として歩けるようにする**VR内覧システム。
物件ごとにURLを発行して、お客様に部屋を見てもらう。

> 全アプリ共通の運用ルールは直下の `CLAUDE.md`、計画は `TODO.md`、作業履歴は `SESSION_LOG.md`。

## 何ができるか

- THETAの写真を放り込むと、**AIが奥行きを推定**して球体を凹凸に変形する
  （ただの360度写真ではなく、手前と奥が立体的に見える）
- 部屋どうしを**ピンで繋いで移動**できる（玄関→廊下→洋室…と歩ける）
- 完成した空間は**自社サーバーへFTPで公開**され、URLをお客様に送るだけで見てもらえる

| 用途 | URL |
|---|---|
| 管理・作成（社内） | `http://localhost:8512/` （社内LANは `192.168.1.105:8512`） |
| お客様向け公開 | `https://daikyocorp.co.jp/vr/#/property/<id>` |

## 構成（2プロセス）

```
ブラウザ（React + Three.js / port 8512）
   ├ 物件一覧 /            … 公開済み物件を一覧（daikyocorp.co.jp/vr/index.json を読む）
   ├ 新規作成 /admin       … 写真をアップ → AI解析 → ピン配置 → 公開
   ├ 閲覧     /property/:id … お客様が見る画面
   └ 編集     /edit/:id     … 公開済み物件の差し替え・ピン修正
        │
        │ ローカルAPI（http://localhost:8523）
        ▼
   server/server.js（Express / port 8523）── FTP ──▶ daikyocorp.co.jp:/www/htdocs/vr/
```

- **AI解析はブラウザの中で完結する**（サーバーへ画像を送らない）。
  Transformers.js が WebWorker（`src/aiWorker.ts`）でモデルを動かす。
- **サーバー側（8523）は「FTPで上げ下ろしするだけ」**。データベースは持たない。
  物件の情報は公開先の `index.json` と `<id>/meta.json` が正典。

### 使っているAIモデル（どちらもブラウザ内推論・APIキー不要）

| 役割 | モデル |
|---|---|
| 奥行き推定 | `onnx-community/Depth-Anything-V2-Small-ONNX` |
| 超解像 | `Xenova/swin2SR-classical-sr-x2-64` |

### 3D化のしくみ

`THREE.SphereGeometry(10, 128, 64)` の各頂点を、推定した深度マップの値で
**内外に押し引き（displacement）** している。写真をテクスチャとして貼った球の内側から見ると、
奥行きのある空間に見える。`displacement` は画面から調整できる（強すぎると歪む）。

## 起動

```bash
# 画面（8512）… 起動のたびに必ず再ビルドする（古いdistを配信しないため）
bash run.sh

# FTP APIサーバー（8523）
cd server && bash run.sh
```

常時起動（launchd・メインPCのみ）:
`com.shinsei.theta-viewer`（8512）と `com.shinsei.theta-viewer-api`（8523）の2本。

## セットアップ

```bash
npm install
cd server && npm install
```

**FTPの接続情報は `server/ftp-config.json`**（`ftp-config.example.json` をコピーして作る）。
**このリポジトリは公開されているので、接続情報は絶対にコミットしない**（gitignore済み）。
環境変数 `FTP_HOST` / `FTP_USER` / `FTP_PASS` / `FTP_ROOT` でも渡せる。

## はまりどころ（調べた事実。次の担当が繰り返さないため）

- **FTP APIのポートは 8523**。以前 8519 と書かれていたことがあるが、それは
  `owner-payout-tracker` と重複していた**誤り**。コード（`server/server.js`）の `PORT = 8523` が正。
- **`run.sh` は毎回 `npm run build` してから `vite preview` する。**
  ビルドを省くと古い `dist/` を配信し続け、「直したのに変わらない」になる。
- **launchd は PATH が最小**（`/usr/bin:/bin:/usr/sbin:/sbin`）で node / npm が見えない。
  `run.sh` の冒頭で `/opt/homebrew/bin` などを足しているのはそのため。**消さないこと。**
- **`run.sh` は `--host 0.0.0.0`**（社内LAN共有のため意図的）。
  サブPCで動作確認するときは社内LANに晒さないよう気をつける。
- ルーティングは **HashRouter**（`/#/property/:id`）。静的ホスティング（FTP先）で
  リロードしても404にならないようにするための選択。BrowserRouterへ変えるとお客様のURLが壊れる。
- `src/firebase.ts` という名前だが、**Firebase は使っていない**（`isConfigured = true` の固定値と
  HTTP/FTP経由のデータ取得だけ）。名残の名前なので、中身から役割を判断すること。

## 主要ファイル

| ファイル | 役割 |
|---|---|
| `src/Router.tsx` | 4画面のルーティング（一覧 / admin / 閲覧 / 編集） |
| `src/PanoramaViewer.tsx` | 球体の生成・深度による変形・ピンの配置とクリック判定 |
| `src/aiWorker.ts` | WebWorker。超解像 → 奥行き推定 → 深度マップを返す |
| `src/firebase.ts` | 公開先(HTTP)とローカルAPIの呼び出しをまとめた層（Firebaseではない） |
| `src/pages/` | `PropertyListPage` / `AdminPage` / `ViewerPage` / `EditPage` |
| `server/server.js` | FTPで公開先へ上げ下ろしする Express API（8523） |
