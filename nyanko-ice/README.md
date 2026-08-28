# にゃんこアイス 🍦

落ち物系ソートパズル。**ゲーム本体は `www/index.html` の1枚**（外部ライブラリ無し・単体で動く）。
iOS アプリは Capacitor で同じ1枚を包んでいる。

## 広告は入っていない（2026-08-28 にすべて外した）

もともと AdMob（バナー／3ステージごとの全画面／ゲームオーバー時の動画リワード）が
入っていたが、**オーナー判断で「一旦、広告なしで出す」**ことにしたため、次を全部削除した。

| 消したもの | |
|---|---|
| `www/index.html` | 広告のCSS・DOM・`initAds` / `showInterstitial` / `showRewarded` とブラウザ用モック |
| `capacitor.config.json` | `plugins.AdMob`（アプリIDごと） |
| `package.json` | `@capacitor-community/admob` |
| `ios/App/App/Info.plist` | `GADApplicationIdentifier` と `NSUserTrackingUsageDescription` |
| `ios/App/Podfile` | `GoogleUserMessagingPlatform`（AdMobの同意取得SDK） |

**ゲームオーバーの「コンテニュー」は残した。** 動画を見る代わりに無条件で押せる
（ボタンの文言も `🎬 動画を見てコンテニュー` → `▶ つづきから` に変えた）。
広告を戻すときは、コミット `942174fe` 以前の同ファイルを見ればすべて揃う。

**この結果、アプリは外部と一切通信しない。** 第三者SDKも無く、集めているデータも無い
（App Store の「プライバシー」では「データを収集しません」）。

## セットアップ・ビルド

```bash
cd ~/nyanko-ice
npm install
npx cap sync ios
xcodebuild -workspace ios/App/App.xcworkspace -scheme App … archive   # 手順は下の「App Store へ出す」
```

**`ios/` は gitignore。** 別PCでは `npx cap add ios` から作り直す（そのとき Podfile に
広告SDKが入っていないことを確認すること）。

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
