# ひよこ防衛軍（piyo-defense）

カラスの大群から地球を守るレーン制タワーディフェンス。全20ステージ × 5Wave。
HTML + Canvas 単体（フレームワーク無し）。GitHub Pages で公開、Capacitor で iOS 化できる形。

```
index.html      画面の器（canvas 1枚）と書体の読み込み
style.css       @font-face（同梱フォント）と canvas の配置
game.js         状態遷移・入力・ゲームループ・当たり判定
js/render.js    絵を描く関数（背景・地面・ひよこ・カラス・ボス・タワー）
js/ui.js        画面ごとのUI（タイトル・HUD・図鑑・実績・設定・結果）
js/entities.js  敵とボスの挙動
js/upgrades.js  強化・ショップ
js/save.js      localStorage（ハイスコア・図鑑・実績・コイン）
js/sound.js     効果音10種＋BGM（WebAudioの合成音。音声ファイルは無い）
assets/fonts/   Zen Maru Gothic のサブセット（tools/fetch-font.py が作る）
tools/          fetch-font.py
www/            Capacitor の webDir。**上のファイルのコピー**（後述）
```

## 動かして確かめる

```bash
cd piyo-defense
python3 -m http.server 8899        # file:// で開かないこと（後述）
# → http://127.0.0.1:8899/
```

**`file://` で開くと書体が当たらない。** Chrome が file:// のフォント取得を止めることがある。
実運用は影響なし（GitHub Pages も Capacitor もHTTP）。検証は必ずHTTP経由で行う。

**ブラウザのキャッシュが強い。** `js/*.js` を直したのに画面が変わらないときは、
まずキャッシュを疑う（2026-08-28にこれで30分溶かした）。`./va.sh` / Playwright とも
プロファイルを持ち回るので、`Cache-Control: no-store` を返すサーバで開くか、
ブラウザを開き直すのが確実。URL に `?v=<秒>` を付けても index.html しか更新されない。

## はまりどころ（調べて分かったこと）

### canvas に指定しただけでは Web フォントは読み込まれない

`ctx.font = '46px "Zen Maru Gothic"'` と書いても、**DOMに1文字も無ければブラウザは
フォントを取りに行かない**（`@font-face` は使われて初めて読まれる）。
`game.js` の冒頭で `document.fonts.load()` を明示的に呼んでいる。消さないこと。

読めているかの確認:

```js
document.fonts.check('900 16px "Zen Maru Gothic"')   // → true
```

### 画面の文言を増やしたら fetch-font.py を流し直す

同梱フォントは**画面に出る文字だけ**に絞ってある（全部入れると数MB）。
文言を足したまま流し忘れると、増やした文字が □（豆腐）になる。

```bash
python3 tools/fetch-font.py --check   # いま何字使っているか
python3 tools/fetch-font.py           # assets/fonts/ を作り直す
```

ソース全体を走査してはいけない。日本語コメントを大量に書いているので、
そのまま拾うと漢字が数百字になりフォントが倍以上になる。
`screen_text()` が **HTMLのテキストとJSの文字列リテラルだけ**を拾っている。

### 背景の色は「地平線側を一番明るく」する

`js/render.js` の `_SBG` は t=天頂 / m=中空 / b=地平線側。**b が一番明るい。**
旧版は逆で（b が最暗、ステージ20は `#000000`）、画面の2/3が黒一色になり
「何も無い画面」に見えていた。加えて黒いカラスが空に溶けて**遊びにくかった**。

暗いのは装飾ではなくコントラストの都合:
- 空の下半分を明るくする → 暗い敵の輪郭が立つ
- 空の上半分は暗いまま → 星と、黄色いひよこの弾が見える

敵には `drawCrow` の中で**輪郭光**（月あかり想定の淡いハロー）を1枚敷いている。
これが無いと、どんな空の色でも必ずどこかで敵が埋もれる。

### www/ は手でコピーする（cap sync ではソースが同期されない）

`capacitor.config.json` の `webDir` が `www` なので、**iOS版に載るのは `www/` の中身**。
ルートを直しただけでは反映されない。触ったら必ずコピーする:

```bash
cp index.html style.css game.js www/
cp js/*.js www/js/
cp assets/fonts/*.woff2 www/assets/fonts/
npx cap sync                        # そのあとで
```

`assets/` が増えているので、**コピーを忘れると書体だけ入らない**（豆腐になる）。

### GitHub Pages への公開は自動ではない

リポジトリ直下 `.github/workflows/deploy.yml` の `DEPLOY_FOLDERS` に
**このアプリは入っていない**（2026-08-28 時点）。main を push しても公開版は変わらない。
自動にするなら `piyo-defense` を足す（このアプリは直下に `index.html` があるので
`nyanko-ice:www` のような `:` 付き指定は不要）。**外部公開なのでオーナーの指示を待つこと。**

## 画面の座標について

描画は 390 × 844 の固定キャンバスで、CSS で拡大している（`resize()`）。
タップ判定は `game.js` の `handleMenuTap` に**生の座標で直書き**されているので、
**ボタンの位置を動かしたら、そこも直すこと**。
