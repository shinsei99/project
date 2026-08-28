# App Store 用スクリーンショット

```bash
./screenshots/shoot.sh title gate battle boss combo over            # iPhone 17 Pro Max
DEVICE=ipad ./screenshots/shoot.sh title gate battle boss combo over # iPad Pro 13
```

| フォルダ | 中身 | git |
|---|---|---|
| `shots/` `shots-ipad/` | シミュレータの素の解像度（1320×2868 / 2064×2752） | **入れない**（1回ぶんで65MB。撮り直せる） |
| `upload/iphone` | 1290×2796（6.9型・`APP_IPHONE_67`） | 入れない |
| `upload/iphone65` | 1284×2778（6.5型・`APP_IPHONE_65`）。6.9型が弾かれたときの逃げ道 | 入れない |
| `upload/ipad` | 2048×2732（iPad Pro 12.9型） | 入れない |
| `shoot.sh` `shot-boot.js` | 撮影の仕組み | **入れる** |

**シミュレータの素の解像度のままでは App Store Connect に弾かれる。** `sips` で上の寸法へ直す:

```bash
sips -z 2796 1290 shots/title.png --out upload/iphone/title.png
sips -z 2732 2048 shots-ipad/title.png --out upload/ipad/title.png
```

## 仕組み（タップを使わない理由）

このMacのターミナルには「アクセシビリティ」権限が無く、シミュレータへタップを送れない
（`simtap.py` が使えない）。そこで **画面の状態をコードで作る細工**（`shot-boot.js`）を
`www/index.html` の IIFE の中へ差し込んだビルドを、1画面につき1回作って撮る。

- **構図は撮る直前（9.2秒）に作り、`G.running=false` で止める。**
  起動直後に作ると、撮影までの十数秒でゲートも敵も流れて別の絵になる。
  ウェーブ数も `update()` が `G.t` から計算し直すので、止めないと 1 に戻る
- **起動から12秒待ってから撮る。** 6秒だと WebView の描画が間に合わず真っ黒になる
- 撮影後、`ios/App/App/public/index.html` は `www/index.html` で自動的に戻る
  （**配信物に細工を残さない**）。念のため Archive 前に
  `grep -c "shotSetup\|SHOT" ios/App/App/public/index.html` が 0 であることを確かめるとよい
