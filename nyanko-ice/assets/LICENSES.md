# 同梱している素材のライセンス

このフォルダに入っているものは、すべて **商用利用可・埋め込み可・再配布可** のものだけ。
`shinsei99/project` は **public リポジトリ**で、GitHub Pages で配信し、さらに
**App Store に出す（＝商用）**ので、この3条件を満たさない素材は入れない。

## フォント

| ファイル | 書体 | 出どころ | ライセンス |
|---|---|---|---|
| `fonts/ZenMaruGothic-500.woff2` | Zen Maru Gothic Medium | [Google Fonts](https://fonts.google.com/specimen/Zen+Maru+Gothic) | SIL Open Font License 1.1 |
| `fonts/ZenMaruGothic-900.woff2` | Zen Maru Gothic Black | 同上 | 同上 |

- 作者: Yoshimichi Ohira
- SIL OFL 1.1 は **商用利用可・改変可・埋め込み可・再配布可**。
  制約は「フォント単体を有償で売らないこと」と「Reserved Font Name を変えずに改変版を配らないこと」で、
  アプリへの同梱はどちらにも当たらない。帰属表示の義務も無い（このファイルは記録のために書いている）。
- Google Fonts は CSS/API 経由の自動取得を認めているので、`tools/fetch-font.py` で取得している。
- 同梱しているのは**画面に出る文字だけに絞ったサブセット**（約330字・各32KB）。
  丸ごとの Zen Maru Gothic は数MBあり、iOSアプリに載せるには重すぎるため。
  **`www/index.html` の文言を変えたら `python3 tools/fetch-font.py` を流し直すこと**
  （流し忘れると、増やした文字が □ になる）。
- OFL 全文: https://openfontlicense.org/

## 音

**音のファイルは同梱していない。** BGM も効果音も `www/index.html` の中で
WebAudio により合成している（容量が増えず、素材のライセンスを持ち込まずに済むため）。

録音した素材に差し替えるときは `www/index.html` の `USE_FILES` の上に手順を書いてある。
**持ち込んでよいのは商用可かつ再配布可のものだけ**:

| 使ってよい | 理由 |
|---|---|
| [効果音ラボ](https://soundeffect-lab.info/) | 商用利用可・クレジット表記不要 |
| CC0 の素材（Kenney など） | 権利放棄されており再配布も可 |

| 使わない | 理由 |
|---|---|
| 魔王魂 | **クレジット表記が必須**。アプリ内に表記欄を作らない限り使えない |
| いらすとや | 1制作物21点以上は有償。素材そのものを組み込む用途は規約がグレー |
| DOVA-SYNDROME | **素材ごとに規約が違う**ので、1曲ずつ確認しないと使えない |

## 画像

**同梱していない。** 背景・ネコ店長・アイス・コーンはすべて canvas で描いている。
外部のイラスト素材を混ぜると画風が衝突するため、意図的にそうしている。
