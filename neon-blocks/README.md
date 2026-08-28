# ネオンブロック（neon-blocks）

全100面のポリオミノパズル。**ゲーム本体は `index.html` の1枚**（`www/index.html` は Capacitor が包む用の同じもの）。
App Store には **1.0.3 / build 4 が配信中**（2026-08-24 に API で確認）。

## iOS のこと

- **`ios/` は git に入っていない。** 別PCや作り直しのときは `npx cap add ios` から作る
- **そのとき `MinimumOSVersion`（動く最低のiOS）が既定の 13.0 に戻る**ので、下の値を入れ直すこと

### MinimumOSVersion は 15.0 にしてある（2026-08-28）

**2027年春以降、iOS 15.0 未満のアプリは App Store へアップロードできなくなる**
（アップロード時に Apple から警告 90068 が出る）。配信中の build 4 は **13.0** のままなので、
**次に更新するときに 15.0 で出す**。設定はこのMacで済ませてあり、**ビルドは通ることを確認済み**
（`** BUILD SUCCEEDED **`）。まだ Archive もアップロードもしていない。

```
ios/App/Podfile                        platform :ios, '15.0'
ios/App/App.xcodeproj/project.pbxproj  IPHONEOS_DEPLOYMENT_TARGET = 15.0（4か所）
→ 変えたら pod install
```

**機種が切り捨てられる心配はほぼない。** iOS 13 が動く機種（iPhone 6s 以降）は
そのまま iOS 15 にも上げられるため、影響するのは「OSを更新していない人」だけ。

### 次に出すときの手順

```bash
cd ~/neon-blocks
npx cap sync ios
cd ~ && ./ios-build-guard.sh neon-blocks --bump     # ★build 5 以上へ（配信中は build 4）
```

Archive〜アップロードは GUI 不要。`scrapmemo-petapeta/RELEASE_NOTES.md` 末尾の3コマンドと同じ
（このアプリも Capacitor＝CocoaPods なので **`-workspace ios/App/App.xcworkspace`** を使う）。

## 6つのゲームが入っている（2026-08-29 統合）

**きっかけ**: 2026-08-29 に3本まとめて Guideline 4.3(a)（スパム）でリジェクトされた。
アカウント全体の出し方（2か月で9本・同じ Capacitor の殻・似た書式）を見られていると判断し、
**小さいゲームを個別に出すのをやめ、配信中のこのアプリ1本にまとめる**方針にした。
**App 記録は1本も増えない**ので、4.3(a) に対して言葉ではなく形で答えられる。

### 構成

```
www/
  index.html            ← ネオンブロックス本体（★アプリを開くとこれが出る）
  games/
    _switch.js          ← 下の「ほかのあそび」帯（全ゲームが読み込む）
    _back.js            ← 旧方式の名残。空にしてある
    blocks/index.html   ← 本体への転送だけ（重複を置かないため）
    escape/  ice/  gravity/  cyborg/  piyo/   ← 各ゲームを丸ごと
```

**入口画面を挟まない。** 開いたらいままでどおりネオンブロックスが出る。既存ユーザーの体験が
変わらず、掲載名と中身も食い違わない（2.3 の観点）。切り替えは**画面下の細い帯**で、
押したときだけ6本がせり上がる（3列×2行・中央寄せ・最大560px）。

**各ゲームのコードには手を入れていない。** `<script src="../_switch.js"></script>` を1行足しただけ。
だから各ゲームは単体でも今までどおり動くし、Web版（gh-pages）とも中身がずれない。

### 気をつけること

- **進み具合は混ざらない。** `localStorage` のキーがゲームごとに違うことを実測で確認済み
  （`neonblocks_mute` / `nyanko_ice_*` / `neko_escape_*` / `color_gravity_*` / `cyborg_*` / `piyo_*`）
- **ゲームを足すときは3か所**: `www/games/<名前>/` にフォルダを置く → そのHTMLに `_switch.js` を
  読み込ませる → `_switch.js` の `GAMES` に1行足す
- 帯は `position:fixed` なので、**ゲーム側の下部UIと重ならないか必ず実機幅で見る**
  （390×844 で6画面を確認済み）
- **提出は保留中**（4.3(a) の返事待ち）。出すときは build 番号を必ず +1
