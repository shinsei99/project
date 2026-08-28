# App Store Connect に入れる文言（カラー・グラビティ）

そのままコピーして使えるようにしてある。文字数は App Store Connect の上限。
**流し込みは `python3 push-metadata.py --apply`**（この1ファイルを正とする。画面へ手で写さない）。

---

## なぜこの文言なのか（先に読む）

**提出前に App Store を実測した**（2026-08-28・iTunes Search API）。KeyTag が
Guideline 4.3(a)（スパム＝他の開発者のアプリと似ている）で差し戻された教訓による。

| 調べたこと | 結果 |
|---|---|
| `カラー・グラビティ` `カラーグラビティ` `Color Gravity` の完全一致 | **なし**（jp・us とも。名前は空いている） |
| 近い名前 | `Color Gravity Switch`（Jaroslaw Miazga）／`Gravity Grid: Color Drop`（Tazigra LLC）。**どちらも別ジャンル**（前者は落下方向を切り替えるアクション、後者は落ち物） |
| 同ジャンル（重力スイングバイ系パズル） | `Moonshot`（Noodlecake）／`Gravity Slingshot: Orbit Orbit`（Leon Glas）／`Voyager: Grand Tour`（Rumor Games）／`Gravity Well - Physics Puzzle`／`GraviTee` |

**ここは量産テンプレの棚ではない**（ソートパズルのように同一構造のアプリが並ぶ棚とは違い、
上記はどれも作者も中身も別物）。それでも 4.3(a) を踏まないように、
**このゲームにしかない仕組み**を名前・サブタイトル・説明の先頭に置く。

| ✅ 前に出す | なぜ効くか |
|---|---|
| **色が混ざる**（赤＋青＝紫／3色そろえば白）。目標の結晶と同じ色でなければ弾かれる | 重力パズルに「加法混色」を持ち込んでいるものが見当たらない。**これが中核** |
| **属性一致の重力** — 星は「自分が持っている色」の惑星からしか引力を受けない | 色が変わると軌道そのものが変わる。色と物理が結びついている |
| **広告なし・課金なし・通信なし** | この棚の無料アプリはほぼ広告収益型。最も分かりやすい違い |
| **全20面すべてに正解が用意してある**（「正解を見る」で正解の軌道を再現できる） | 自動生成ではなく、1面ずつ解いて作った証拠。詰んで投げ出すことがない |
| **画像素材が0枚**（惑星もブラックホールも結晶も、その場で描いている） | 素材集の使い回しではない |

❌ 名前や説明の主役を「物理パズル」にしない（それだけでは棚に埋もれる）。

---

## 名前（30字以内）

```
カラー・グラビティ
```

- 完全一致の既存アプリなし（jp・us・2026-08-28 実測）
- **ホーム画面の表示名は `カラグラ`**（`capacitor.config.json` の `appName`）。
  9文字はホーム画面で切れるため、掲載名とは別にしている（KeyTag と同じ考え方）

---

## サブタイトル（30字以内）

```
広告なし。色が混ざる重力パズル
```

**「広告なし」を最初に置く。** この棚で最も効く差別化。
そのあとに、このゲームの中核である「色が混ざる」を置く。

---

## プロモーション用テキスト（170字以内）

**新しいビルドを出さずにいつでも変更できる欄。**

```
広告も課金もありません。インターネットにもつながりません。引いて、離して、あとは重力にまかせる。ゲートをくぐるたび星の色が混ざり、色が変われば引かれる惑星も変わります。全20面、すべてに正解が用意してあります。
```

---

## キーワード（100字以内・カンマ区切り／スペースを入れない）

```
パズル,重力,物理,色,混色,宇宙,惑星,ブラックホール,スリングショット,軌道,広告なし,無料,オフライン,ステージ,ひまつぶし,頭脳,思考,ネオン
```

- 名前に入っている語（カラー・グラビティ）はキーワードに入れない（重複は無駄）

---

## 説明（4000字以内）

**★App Store の説明に絵文字は入れられない**（`INVALID_CHARACTERS` で 409 になる。
にゃんこアイスで実際に踏んだ）。以下は絵文字なし。

```
引いて、離して、あとは重力にまかせる。
惑星のあいだを縫って、星を結晶へ届ける宇宙のパズルです。

■ 色が混ざる
星は赤・青・黄の三原色でできています。
色のついたゲートをくぐると、その色が星に混ざります。
赤＋青は紫、赤＋黄は橙、青＋黄は緑、三色そろえば白。
結晶と同じ色になって当たればクリア。色がちがうと弾かれます。

■ 色が変われば、軌道も変わる
星は「自分が持っている色」の惑星からしか引力を受けません。
青い星は青い惑星にだけ引かれ、赤い惑星のそばは素通りします。
どのゲートを、どの順に通るか。それがそのまま軌道の設計になります。

■ 引く前に、道筋が見える
砲台をドラッグしている間、飛んでいく道すじが点で表示されます。
色が変わる場所も、惑星に曲げられる様子も、撃つ前に確かめられます。
運まかせにはなりません。

■ 全20面、すべてに正解があります
1面ずつ手で作り、すべての面で「必ずクリアできる撃ち方」を確かめてあります。
どうしても解けないときは「正解を見る」を押してください。
正解の軌道をそのまま再現します。詰んで投げ出すことはありません。

■ 星は3つまで
残弾を1つも使わずにクリアすると星3つ。2つまでで星2つ、それ以上で星1つ。
解けた面にもう一度挑んで、星を取り直せます。

■ 待ちうけるもの
ガスをまとった惑星、吸い込むブラックホール、色を選んで跳ね返す鏡、
そして三色を束ねた白い結晶。

■ このアプリについて
・広告は表示しません。アプリ内の課金もありません。
・インターネットにつながりません。機内モードでも最後まで遊べます。
・個人情報を一切集めません。進み具合と音の設定は端末の中だけに残ります。
・効果音も音楽も、その場で合成して鳴らしています。音はいつでも切れます。
・惑星もブラックホールも結晶も、画像を1枚も使わずその場で描いています。

静かな宇宙で、軌道を一本ずつ描いてください。
```

---

## 審査ノート（App Review Information → Notes）

```
This is a single-player physics puzzle game. No account, no login, no network access.

- The app works fully offline (airplane mode). It makes no network requests at all.
- No advertising SDK, no analytics SDK, no third-party SDK of any kind.
  The only framework is Capacitor (WebView shell).
- No in-app purchase. No user-generated content. No user data is collected.
  Only the stage progress and the sound on/off flag are stored locally (localStorage).
- Content is suitable for all ages (4+). No violence, no text input, no external links
  except the support and privacy pages.

Regarding Guideline 4.3 (Spam):
We searched the App Store before submitting. The core mechanic of this game is
ADDITIVE COLOR MIXING combined with attribute-matched gravity, which we could not find
in any existing gravity/slingshot puzzle:
  1. The star carries a set of primary colors (red, blue, yellow). Passing through a
     colored gate adds that color (red + blue = purple, all three = white).
  2. A planet only attracts the star if the star already carries that planet's color.
     Changing color therefore changes the trajectory itself.
  3. The star must reach the crystal WITH THE MATCHING COLOR, otherwise it bounces off.
All 20 stages are hand-made and each ships with a verified solution vector, so the
"Show solution" button always replays a trajectory that actually clears the stage.
All artwork is drawn procedurally on a canvas at runtime; no stock art is used
(the app bundle contains zero image assets other than the app icon).

The full source of the game is public:
https://github.com/shinsei99/project/tree/main/color-gravity
The web version can be played in a browser here:
https://shinsei99.github.io/project/color-gravity/
```

---

## その他の欄

| 欄 | 値 |
|---|---|
| サポートURL | `https://shinsei99.github.io/project/color-gravity/support.html` |
| プライバシーポリシーURL | `https://shinsei99.github.io/project/color-gravity/privacy.html` |
| マーケティングURL | （空欄） |
| プライマリカテゴリ | ゲーム（`GAMES`）／サブカテゴリ **パズル**（`GAMES_PUZZLE`） |
| セカンダリカテゴリ | **付けない**（KeyTag が 4.3(a) を受けたとき、副カテゴリを外して整理した経緯に合わせる） |
| 年齢制限 | 4+（暴力・不適切表現なし・Web閲覧なし） |
| 価格 | 無料 |
| App のプライバシー | **データを収集しない**（Data Not Collected） |
| 著作権 | `2026 SHINSEI PROPERTY MANAGEMENT.K.K.` |
| 対応デバイス | iPhone（縦向きのみ）／iPad（全方向） |
| 最低OS | iOS 15.0（Capacitor 8 の既定。2027年春からの必須要件を満たす） |
