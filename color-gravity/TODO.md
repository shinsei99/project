# カラー・グラビティ — TODO

## いま止まっているところ（2026-08-28 メインPC）

**App Store 提出の直前で、オーナー待ちが1件だけある。**

| # | 内容 | 誰が |
|---|---|---|
| 1 | **App Store Connect で「App 記録」を作る**（名前 `カラー・グラビティ` / バンドルID `com.shinsei99.colorgravity`）。**API では新規Appを作れない**ので画面での作業。これが無いと `altool` が `Cannot determine the Apple ID from Bundle ID` で止まる（実測） | **オーナー** |
| 2 | 記録ができたら、検証 → アップロード → 文言・スクショの流し込み | こちら（機械で実行） |
| 3 | 価格（無料）／App のプライバシー（データを収集しない）／年齢制限（4+）／**審査へ提出** | **オーナー**（画面でしか設定できない） |
| 4 | **音を一度聴く。** 鳴ることは確認済みだが**心地よいかは未確認**（こちらでは聴けない）。気に入らなければ `www/assets/audio/` に素材を置いて `USE_FILES=true` にし、build 2 で出し直す | オーナー |

手順とつまずき所は **`RELEASE.md`**。文言の正本は **`store-text.md`**。

## 完了（2026-08-28 メインPC）

### ① 見た目・音・手触りの作り込み（にゃんこアイスと同じ方針）

- [x] 音（効果音10種＋BGM＋🔊。WebAudio合成・`USE_FILES` で差し替え可）
- [x] 書体（Orbitron ＋ Zen Kaku Gothic New を使う文字だけ同梱・96.4KB）
- [x] 進捗の保存（localStorage。以前はリロードで全部消えていた）
- [x] ★評価（残弾で3段階。ステージ選択にも表示）
- [x] 描画（惑星の縞と輪／降着円盤／二重リングのゲート／宝石の結晶／星空3層の視差）
- [x] 手触り（スリングショットのゴムと力ゲージ／画面の揺れ／クリアの閃光と破片）
- [x] タイトル画面（音を起こす入口も兼ねる）
- [x] ヒントを盤外へ／スキップ先も解放する

### ② iOSアプリ化 → 提出直前まで

- [x] 本体を `www/` へ移して Capacitor 8 で iOS 化（`com.shinsei99.colorgravity`・最低OS 15.0）
- [x] iPhone は縦のみ／iPad は全方向。ノッチとホームバーを避ける
- [x] アプリアイコン（`tools/make-icon.py`。惑星＋輪＋軌道＋三原色のゲート）
- [x] `www/support.html` / `www/privacy.html` ＋ `DEPLOY_FOLDERS` を `color-gravity:www` へ
- [x] ストア文言（`store-text.md`）。**提出前に App Store を実測して 4.3(a) の根拠を用意**
- [x] スクリーンショット iPhone 5枚 + iPad 5枚（`screenshots/upload/`）
- [x] **1.0 / build 1** を Archive → ipa 書き出し（1.58MB）
- [x] 配信物の実測（広告SDK・解析SDKなし／撮影用の細工0件／外部通信なし）

**物理は一度も壊していない**（`python3 tools/verify_solutions.py` が全20面 win）。

## いつかやるなら

- ステージ追加／タイムアタック／クリア後の軌道リプレイ。
  どれも新しい面の `sol`（正解の発射ベクトル）を解く必要があるが、**ソルバーがリポジトリに無い**。
  作るなら `tools/verify_solutions.py` と同じ抜き出し方（物理区間を node で実行）で書ける。
- Android（`npx cap add android`）。いまは iOS だけ。
