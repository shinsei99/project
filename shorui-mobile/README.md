# 書類キャビネット スマホ用（shorui-mobile）

紙の書類をスマホで撮って **Dropbox の「書類取込」フォルダ** に送るだけのWebアプリ。
送られた写真は Dropbox 経由でメインMacに同期され、**PC用「書類キャビネット」(port 8528) の「📁 取込」タブ**がAIで目録化して整理する。

```
[スマホ] Vercelのこのアプリ（URLで開く / ホーム画面に追加でPWA）
   物件名を入力 → カメラで数枚撮影 → 送信
        │  /api/upload が Dropbox API でアップロード
        ▼
[クラウド] Dropbox: /書類取込/<日時_物件名>/ shot_01.jpg … + meta.json
        │  Dropboxが自動sync
        ▼
[Mac] ~/Library/CloudStorage/Dropbox-個人/CLAUDE/書類取込/…
        │
[PC] 書類キャビネット「📁 取込」タブ → AI目録化 → 保管場所を選んで登録 → 済フォルダへ
```

- 運用モデルは **brain-dump と同じ（Next.js + Vercel）**。
- スマホ側は撮って送るだけ。整理・検索はPC側キャビネットが担当（役割分担）。

---

## セットアップ（初回だけ）

### 1. Dropbox アプリを作る
1. https://www.dropbox.com/developers/apps → **Create app**
2. 「**Scoped access**」→「**Full Dropbox**」を選ぶ（`/書類取込` に書くため App folder では不可）
   - ※ `書類取込` フォルダがある Dropbox アカウント（`Dropbox-個人`）でログインして作ること
3. 作成後 **Permissions** タブで `files.content.write` と `files.content.read` を ON → **Submit**
4. **Settings** タブの **App key / App secret** を控える

### 2. refresh token を取る
```bash
cd shorui-mobile
npm install
DROPBOX_APP_KEY=＜App key＞ DROPBOX_APP_SECRET=＜App secret＞ npm run get-token
```
表示URLをブラウザで開いて「許可」→ 出た認可コードを貼る → `DROPBOX_REFRESH_TOKEN=...` が出る。

### 3. Vercel にデプロイ
1. このフォルダを Vercel の新規プロジェクトとして import（brain-dump と同じ要領）
2. **Environment Variables** に3つ設定:
   - `DROPBOX_APP_KEY`
   - `DROPBOX_APP_SECRET`
   - `DROPBOX_REFRESH_TOKEN`
3. Deploy → 発行URLをスマホで開く。iPhoneは共有→「ホーム画面に追加」でアプリ風に使える。

### 4. ローカルで試す場合
`.env.example` を `.env.local` にコピーして3つの値を入れ、`npm run dev` → http://localhost:3000 。

---

## 送られるもの（PC側が読む形）

`/書類取込/<YYYYMMDD-HHMMSS_物件名>/` の中に:
- `shot_01.jpg`, `shot_02.jpg` … 撮った写真
- `meta.json` … `{ property, memo, capturedAt, count, source }`

PC側キャビネットの「📁 取込」タブがこの単位（1フォルダ＝1冊）で読み取り、登録後は
`/書類取込/_済/` に退避する。

## 注意
- Full Dropbox 権限のトークンなので `.env*` は絶対にコミットしない（`.gitignore`済み）。
- 写真は個人情報を含む。Vercelプロジェクトは公開URLだが認証は無いので、URLを共有しないこと
  （必要なら Vercel の Password Protection / Vercel Authentication を後付けする）。
