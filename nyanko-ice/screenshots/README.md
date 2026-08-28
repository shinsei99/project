# スクリーンショットの撮り方（App Store 用）

**画像の実体は git に入れていない**（1枚3MBで10枚＝34MB になるため）。
下の手順でいつでも作り直せる。**作り直したら中身は変わりうる**ので、
「いま App Store に載っているもの」を見たいときは App Store Connect を見ること。

## 1. 撮る（シミュレータ・タップ不要）

```bash
cd ~/nyanko-ice
./screenshots/shoot.sh start play stack clear gameover              # iPhone 17 Pro Max → shots/
DEVICE=ipad ./screenshots/shoot.sh start play stack clear gameover  # iPad Pro 13    → shots-ipad/
```

**タップを送らずに画面を作っている。** このMacのターミナルには「アクセシビリティ」権限が無く、
シミュレータへタップも ⌘V も送れない（`simtap.py` が使えない）。そこで
`shot-boot.js` を **`www/index.html` の IIFE の中**（末尾の `})();` の直前）へ差し込んだ
ビルドを画面ごとに作り、起動して `simctl io screenshot` で撮っている。

- `www/index.html` は**触らない**（配信物の正）。細工が入るのは `ios/App/App/public/index.html` だけ
- 撮り終わると `public/index.html` を `www/` の中身で上書きして戻す
- **Archive の前に `grep -c "shotSetup" ios/App/App/public/index.html` が 0 であることを確認する**

画面の中身（`shot-boot.js` の分岐）:

| 名前 | 何の画面か |
|---|---|
| `start` | ステージ1のはじまり。店内・ねこ店長・ちゅうもんが見える |
| `play` | ステージ3。コーンを1本選んだ状態（枠が光る） |
| `stack` | ステージ6。積み上がって難しくなった状態 |
| `clear` | ステージクリアのパネル |
| `gameover` | ゲームオーバー（`▶ つづきから` が見える） |

## 2. 寸法を直す（**素の解像度は App Store に弾かれる**）

シミュレータは iPhone 17 Pro Max = 1320×2868、iPad Pro 13 = 2064×2752 で撮る。
App Store が受け付けるのは次の寸法。

```bash
cd ~/nyanko-ice/screenshots
mkdir -p upload/iphone upload/ipad
i=1; for s in start play stack clear gameover; do n=$(printf "%02d" $i)
  cp shots/$s.png      upload/iphone/$n-$s.png && sips -z 2778 1284 upload/iphone/$n-$s.png
  cp shots-ipad/$s.png upload/ipad/$n-$s.png   && sips -z 2732 2048 upload/ipad/$n-$s.png
  i=$((i+1)); done
```

| 種別 | 寸法 | App Store Connect 上の名前 |
|---|---|---|
| iPhone 6.5型 | 1284×2778 | `APP_IPHONE_65` |
| iPad Pro 12.9型（第3世代） | 2048×2732 | `APP_IPAD_PRO_3GEN_129` |

**両方とも必要**（このアプリは `TARGETED_DEVICE_FAMILY = "1,2"` ＝ iPhone と iPad の両対応）。

## 3. 入れる

**ファイル名順がそのままストアの並び順**になるので `01-` `02-` と付ける。
既存のスクショは**全部消してから**入れ直す。

```bash
python3 push-screenshots.py screenshots/upload/iphone --device iphone            # 下見
python3 push-screenshots.py screenshots/upload/iphone --device iphone --apply
python3 push-screenshots.py screenshots/upload/ipad   --device ipad   --apply
```

最後に全部 `COMPLETE` になっていれば成功（`UPLOAD_COMPLETE` は検証中で、少し待てば変わる）。
