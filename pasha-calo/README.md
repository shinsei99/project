# パシャカロ！

料理をパシャっと撮るだけで、AIがカロリーとPFC（たんぱく質・脂質・炭水化物）を推定して記録するダイエットアプリ。

**brain-dump と同じ構成**（Next.js 16 + Vercel + PWA）なので、iPhoneのホーム画面に追加すればネイティブアプリのように使えます。

---

## 機能

1. **初期設定** — 性別・年齢・身長・体重・運動量・目標・目標体重から、ハリス・ベネディクト方程式で1日の目標カロリーを自動計算（あとから手動変更も可）
2. **ホーム** — 今日の摂取カロリーの進捗バー＋PFCバー、現在体重とBMI、今日の記録一覧
3. **撮影＆AI解析** — **無音カメラ**または ライブラリから **最大6枚まとめて** → AIが料理名・カロリー・PFC・アドバイスを推定 → 内容を確認・補正して記録
   - **シャッター音が鳴らない**アプリ内カメラ（`getUserMedia`で映像から切り出す方式。brain-dump と同じ）。音の代わりに画面が一瞬光る
   - 何枚か撮ってから「この◯枚でカロリーを計算」でまとめて解析。同じ食事を別角度で撮ると精度が上がる
   - AIが一番外しやすい「分量」を ×0.5〜×2 のボタンで補正できる
   - 数値は手入力でも微調整可、食事区分（朝/昼/夜/間食）も選べる
4. **体重タブ** — 体重記録、BMIと肥満度判定（日本肥満学会基準）、目標体重までの進捗バー、**推移グラフ**（外部ライブラリ不使用のSVG）、直近4週間の増減ペースと目標達成予測日
   - 体重を記録すると目標カロリーも自動で再計算される（手動設定時を除く）
5. **履歴** — 日付ごとにグループ化、日合計カロリーを表示、タップで詳細・削除

記録は端末の localStorage のみに保存されます（サーバーには残りません）。
**撮影した写真は解析に送るだけで、端末にもサーバーにも保存しません。**

---

## AIの切り替え（Gemini ⇄ Claude）

`.env.local` の `AI_PROVIDER` で切り替えます。

| | Gemini（既定） | Claude |
|---|---|---|
| 環境変数 | `GEMINI_API_KEY` | `ANTHROPIC_API_KEY` |
| キー取得 | https://aistudio.google.com/apikey | https://console.anthropic.com/settings/keys |
| 費用 | 無料枠あり（個人利用なら十分） | 従量課金（要クレジット購入） |
| 既定モデル | `gemini-2.5-flash` | `claude-opus-5` |

> **注意:** 見積書ジェネレーター等で使っている `claude` CLI（Claude Code）は **Macローカル専用**で、Vercel上では動きません。Claudeを使う場合はAnthropic APIキーが必要です。
> Claude側は安全性フィルタで拒否された場合に自動フォールバックする設定（`fallbacks: "default"`）を有効にしてあります。

---

## セットアップ

```bash
npm install
cp .env.example .env.local   # キーとアクセスコードを記入
npm run dev                  # http://localhost:3003
```

`ACCESS_CODE` は必須です（未設定だと全リクエストを拒否します）。

## デプロイ（Vercel）

```bash
npx vercel --prod
```

Vercelの Project Settings → Environment Variables に `ACCESS_CODE` と、使う方のAPIキー（＋必要なら `AI_PROVIDER=claude`）を登録してください。

## iPhoneへのインストール

1. **Safari** で https://pasha-calo.vercel.app を開く（Chrome不可）
2. 共有ボタン → **ホーム画面に追加**
3. アイコンから起動（アドレスバーなしの全画面表示）

無音カメラはブラウザのカメラ権限が必要で、**HTTPS または localhost でのみ動作します**（社内LANのIP直打ちでは起動しません）。

## アイコン

`public/icon.svg` がマスターです。変更したら以下でPNGを再生成します。

```bash
node gen-icons.mjs   # apple-touch-icon.png(180) / icon-192.png / icon-512.png を出力
```

iOSのホーム画面アイコンはPNGのみ対応のため、`apple-touch-icon.png` が必須です。

---

## 構成

```
app/
  layout.tsx              PWAメタデータ（manifest / apple-web-app）
  page.tsx                画面全部（ログイン・初期設定・ホーム・撮影・履歴・設定）
  api/auth/route.ts       アクセスコード検証
  api/analyze-meal/route.ts  写真→栄養推定
lib/
  ai.ts                   AIレイヤー（Gemini / Claude を切り替え）
  auth.ts                 アクセスコード検証
  nutrition.ts            ハリス・ベネディクト方程式・PFC目標の計算
public/
  manifest.webmanifest    PWAマニフェスト
```

## 注意

AIの推定値はあくまで目安です。医療・治療目的の利用は想定していません。
