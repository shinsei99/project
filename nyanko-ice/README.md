# にゃんこアイス 🍦 — AdMob 本番化セットアップ

落ち物系ソートパズル。ゲーム本体は `www/index.html`（単体で動作）。
広告は **Capacitor + Google AdMob** でネイティブアプリ化して収益化する。

- **ブラウザ**で `www/index.html` を開く → 広告は **DOMモック**（収益なし・動作確認用）
- **ネイティブアプリ**（下記手順）→ **本物のAdMob広告**（バナー／インタースティシャル／動画リワード）

---

## 広告の出しどころ（実装済み）

| 種類 | タイミング | コード |
|---|---|---|
| バナー | 画面下に常時 | `initAds()` → `AdMob.showBanner` |
| インタースティシャル | 3ステージクリアごと | `advanceStage()` → `showInterstitial()` |
| 動画リワード | ゲームオーバーの「動画を見てコンテニュー」 | `showRewarded(continueStage, ...)` |

現状は **Googleの公式テストID** を使用。実機で「Test Ad」と出れば成功。

---

## セットアップ手順

### 1. 依存インストール & プラットフォーム追加
```bash
cd ~/nyanko-ice
npm install
npx cap add ios       # iOS
npx cap add android   # Android（任意）
npx cap sync
```

### 2. AdMob アプリIDをネイティブに設定
`capacitor.config.json` の `plugins.AdMob.appId` は **テスト用**。本番は自分のAdMobアプリIDに変更し、`npx cap sync` で反映。

- **iOS**: `ios/App/App/Info.plist` に `GADApplicationIdentifier`（cap syncで入るが要確認）
  - ATT（トラッキング許可）を使う場合は `NSUserTrackingUsageDescription` も追記
- **Android**: `android/app/src/main/AndroidManifest.xml` の
  `com.google.android.gms.ads.APPLICATION_ID` を確認

### 3. 広告ユニットIDを本番に差し替え
`www/index.html` 内の以下を、AdMob管理画面で発行した本番IDに変更：
```js
const TESTING = true;   // ← 本番リリース時は false
const AD_IDS = {
  ios:     { banner:'...', interstitial:'...', reward:'...' },
  android: { banner:'...', interstitial:'...', reward:'...' },
};
```
変更後は `npx cap sync`。

### 4. ビルド・実行
```bash
npx cap open ios       # Xcodeで実機/シミュレータ実行
npx cap open android   # Android Studioで実行
```

---

## 注意・チェックリスト

- **プラグインのイベント名はバージョン依存**。`showInterstitial` / `showRewarded` 内の
  `addListener('interstitialAdDismissed' / 'onRewardedVideoAdReward' / 'onRewardedVideoAdDismissed', …)`
  は `@capacitor-community/admob` v6 準拠。導入版のドキュメントで名称を確認し、必要なら修正。
- リリース前に **`TESTING=false`** と **本番ID** に必ず切替（テスト中に本番IDを叩くとポリシー違反になり得る）。
- iOSは **App Tracking Transparency** の対応（`requestTrackingAuthorization`）を検討。
- 既存の `piyo-defense/ios` と同じCapacitorワークフローで運用可能。

## ブラウザでの動作確認

**`open www/index.html` では書体が当たらない。** Chrome は `file://` からのフォント取得を
止めることがあり、日本語が OS 標準（ヒラギノ）で描かれる。**HTTP 経由で開くこと。**

```bash
cd ~/nyanko-ice/www && python3 -m http.server 8571 --bind 127.0.0.1
# → http://127.0.0.1:8571/index.html
```

実運用では起きない問題（Capacitor は独自スキームのHTTP、GitHub Pages もHTTP）。
AdMob未接続のためモック広告。ゲーム挙動・広告の出るタイミング確認用。

---

## 見た目のつくり（2026-08-27 に作り替えた）

画面は canvas に手で描いている。**外部の画像素材は1枚も使っていない**（画風が衝突するため）。
座標は 500×760 固定で、次の4層に割ってある。

| Y | 層 | 描くもの |
|---|---|---|
| 0〜112 | 木の看板 | スコア・ちゅうもん・つぎ（`drawSign` / `drawUI`） |
| 112〜344 | 明るい店内 | 丸窓・ペンダントライト・腰壁・ネコ店長（`drawShop` / `drawCat`） |
| 344〜706 | 冷凍ショーケース | きょうの味・コーン・アイス（`drawCase` / `drawCones`） |
| 706〜760 | カウンター | 木のカウンター天板（`drawCounter`） |

**ショーケースの中だけ暗いのは装飾ではない。** アイスはぜんぶ淡い色（バニラ `#FFF6E0` など）で、
明るい地に置くと輪郭が消える。かといって画面ぜんぶを暗くすると「アイス屋」に見えない。
だから**アイスが乗る場所だけ**を冷たい紺にしている。ここを明るくするなら、
先にアイス側の配色を作り直すこと。

### 書体（Zen Maru Gothic・SIL OFL）

`www/assets/fonts/ZenMaruGothic-{500,900}.woff2` を同梱している。商用可・埋め込み可・**再配布可**。

**丸ごとの日本語フォントは数MBあるので、画面に出る文字だけに絞ってある**（各32KB）。

```bash
python3 tools/fetch-font.py          # 取り直す
python3 tools/fetch-font.py --check  # いま何文字使っているかだけ見る
```

> **`www/index.html` の文言を変えたら必ず流し直すこと。** 忘れると増やした文字が □ になる。
> 取得は Google Fonts の css2 API に `text=` を渡す**サーバ側サブセット**なので、
> `fonttools` の導入は要らない。
> スクリプトは **HTMLのテキストとJSの文字列リテラルだけ**を拾う。ソース全体をなめると
> 日本語のコメントまで拾って漢字が306字になり、フォントが 92KB まで膨らむ（実測）。

### 音

**音のファイルは同梱していない。** BGMも効果音も `www/index.html` の中で WebAudio により合成している。

録音した素材に差し替えたいときは:

1. `www/assets/audio/` に `tap.mp3` `place.mp3` … を置く（名前は `SFX_FILES` のとおり）
2. `www/index.html` の **`USE_FILES` を `true`** にする ← コードの変更はこれだけ
3. 見つからないファイルは、そのキーだけ合成音のまま鳴る（落ちない）

**持ち込んでよいのは商用可かつ再配布可の素材だけ**（このリポジトリは public で、App Store にも出す）。
詳細と使ってよい/使わないサイトの一覧は **`www/assets/LICENSES.md`**。

音のオン/オフは画面下のボタン。設定は `localStorage`（`nyanko_ice_sound`）に残る。
iOS は画面を触るまで音を出せないので、`AudioContext` は最初の `pointerdown` で作っている。

---

## Web版を更新するとき（gh-pages）

**`index.html` だけ置いても書体が入らない。** `www/assets/fonts/` も一緒に置くこと。
