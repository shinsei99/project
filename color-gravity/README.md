# カラー・グラビティ（Color Gravity）

宇宙重力 × 加法混色のスリングショット・パズル。全20面。**HTML 1枚で完結**（CDN不要）。
**2026-08-28 に iOS アプリ化した**（Capacitor 8／Bundle ID `com.shinsei99.colorgravity`）。
提出手順は `RELEASE.md`。

- 公開: https://shinsei99.github.io/project/color-gravity/
- 遊び方: 砲台をドラッグして引っ張り、離すと星が発射。ゲートをくぐると色が混ざり、
  結晶と同じ色で当たればクリア。一発で決めると★3つ。

```
色は原色の集合 {R,B,Y}。R+B=紫 / R+Y=橙 / B+Y=緑 / R+B+Y=白
重力は「属性が一致するときだけ」働く。青い星は青い惑星にしか引かれない
```

## ファイル

| | |
|---|---|
| `www/index.html` | 本体。**これ1枚で動く**（物理・描画・音・進捗保存すべて中に入っている） |
| `www/assets/fonts/*.woff2` | 同梱している書体（使う文字だけに絞ったサブセット・計96KB） |
| `www/assets/LICENSES.md` | 同梱物のライセンス。**素材を足すときは必ずここに書く** |
| `www/support.html` `www/privacy.html` | App Store に登録するサポート／プライバシーのページ。**消さない** |
| `tools/fetch-font.py` | 書体を取り直す。**画面の文言を変えたら必ず流す** |
| `tools/verify_solutions.py` | 全20面の「正解を見る」が本当に届くかを機械で確かめる |
| `tools/make-icon.py` | アプリアイコン（1024）を描く |
| `package.json` `capacitor.config.json` | Capacitor 8。`ios/` と `node_modules/` は git に入らない（各PCで作る） |
| `store-text.md` | App Store の文言の**正本**。流し込みは `push-metadata.py` |
| `screenshots/` | 撮影の道具と、App Store へ入れる10枚（iPhone5・iPad5） |
| `RELEASE.md` | 提出の手順・つまずいた所・配信物の実測 |

**`www/` が本体の置き場**（Capacitor の `webDir`）。GitHub Pages も `color-gravity:www` として
ここを公開している。**直下に index.html を戻さないこと**（両方が壊れる）。

## ★ 触るときの決まりごと

### 1. 物理には触らない

`index.html` の `物理ここから 〜 物理ここまで` の区間（定数・`STAGES`・`stepSim`・`computeLaunch`）は、
**各ステージの `sol`（正解の発射ベクトル）を解いたときの実装そのもの**。
重力定数・速度上限・当たり判定の半径を1つ変えるだけで軌道がずれ、20面ぶんの
「💡 正解を見る」が静かに的を外す。

**目視では気づけない。** それらしい弧を描いて外れるだけなので「そういう面」に見えてしまう。
だから見た目をいじったら必ずこれを流す:

```bash
python3 tools/verify_solutions.py     # 20面すべてで win に到達すればOK
```

実際に踏んだ例（2026-08-28）: 鏡で跳ねたときに効果音を鳴らしたくて、`stepSim` の反射部分を
`return 'bounce'` にした。すると**同じフレームのゲート判定と結晶判定が飛ばされて軌道が変わり**、
鏡のある5・7・13・16・19面の正解が外れる。
→ **戻り値は増やさず、`s.bounced` / `s.lastGate` という印だけを付ける**形にした。
`stepSim` はこの2つを読まないので軌道は1ミリも変わらない。

### 2. 文言を変えたら書体を取り直す

日本語は Zen Kaku Gothic New を**使う文字だけ**に絞って同梱している（43KB×2）。
新しい漢字を書いても、フォントを取り直さないと **□（豆腐）** になる。

```bash
python3 tools/fetch-font.py            # 取り直す
python3 tools/fetch-font.py --check    # いま何字使っているか見るだけ
```

見出しは Orbitron（角ばったSF書体）、日本語は Zen Kaku Gothic New（角ゴシック）。
※にゃんこアイスは Zen Maru Gothic（丸ゴシック）＝「かわいい」。こちらは「宇宙・機械」なので
角ばった書体を選んでいる。**狙って変えているので、揃えないこと。**

### 3. 音のファイルは同梱していない

効果音10種もBGMも WebAudio の合成音で、`index.html` の中で作っている。
容量が増えず、素材のライセンスを持ち込まずに済むため。

差し替えたいときは `assets/audio/` にファイルを置いて `USE_FILES = true` にするだけ
（見つからないファイルはそのキーだけ合成音のまま鳴る＝落ちない）。
**入れてよいのは商用可かつ再配布可のものだけ**（効果音ラボ・CC0 など）。

## 検証のしかた

静的HTMLなので、検証の最低ラインは **Console エラー0件 ＋ 画面の目視**。

```bash
# 1. 物理が生きているか（これが一番大事）
python3 tools/verify_solutions.py

# 2. 画面。file:// ではなく HTTP で開くこと（file:// はフォントがCORSで弾かれることがある）
cd ~/color-gravity/www && python3 -m http.server 8099 --bind 127.0.0.1 &
~/va.sh goto http://127.0.0.1:8099/index.html && ~/va.sh shot && ~/va.sh console --errors

# 3. iOSアプリとして。シミュレータで5画面を撮る（タップ不要）
./screenshots/shoot.sh title aim flight clear stages
DEVICE=ipad ./screenshots/shoot.sh title aim flight clear stages
```

**`va.sh` は1台に1つの共有ブラウザ**なので、他のセッションが使っていると取り合いになる
（実際にページを横取りされた）。取り合うくらいなら Playwright で自前のブラウザを立てるほうが早い。

**favicon を置いていないと Console に 404 が1件出続ける。**
本物のエラーが埋もれるので、SVGを data URI で `<link rel="icon">` に直書きしてある。

## 進捗の保存

`localStorage`。キーは2つだけ。

| キー | 中身 |
|---|---|
| `color_gravity_v1` | `{maxUnlocked, stars:{面番号:★数}}` |
| `color_gravity_sound` | `on` / `off` |

★は **残弾を1つも使わずクリアで3・2つまでで2・それ以上で1**。
「正解を見る」で通したときは★1止まり（自分で当てれば上書きできる）。

## 公開（GitHub Pages）

`.github/workflows/deploy.yml` の `DEPLOY_FOLDERS` に **`color-gravity:www`** で入っている
（2026-08-28 に追加）。**main へ push すれば公開版も一緒に更新される。**

- 公開先: https://shinsei99.github.io/project/color-gravity/
- **`www/support.html` と `www/privacy.html` を消さないこと。**
  App Store に登録する必須URLがこの2枚を指す。デプロイは公開先を `rm -rf` して作り直すので、
  リポジトリ側から消すと公開URLも消え、審査に出せなくなる
- 書き方を `color-gravity`（直下）に戻すとデプロイが落ちる（直下に index.html が無いため）
