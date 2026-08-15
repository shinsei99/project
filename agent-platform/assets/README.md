# 素材フォルダ

ここに置いた素材は、各部隊が名前で探して成果物に使います。
**サブフォルダとファイル名がそのまま検索語**になるので、日本語で分かりやすく付けてください。

```
assets/
├── イラスト/   自転車_注意.png、ゴミ出し_カレンダー.png …
├── 写真/       マンション外観.jpg、エントランス.jpg …
├── ピクト/     駐輪禁止.png、ゴミ出し.png …（掲示物で最優先に使われる）
├── ロゴ/       大京商事_ロゴ.png …
├── 音楽/       動画のBGM（.mp3 / .wav）
└── 動画/       差し込み用の動画素材
```

## 使えるフリー素材サイト（2026-08-14 規約確認）

**人がダウンロードして、このフォルダに置いてください。** ダウンロードして使うぶんには
どのサイトも商用利用可・クレジット不要です（直リンクや自動収集がNGなだけ）。

| サイト | 素材 | 備考 |
|---|---|---|
| [標準案内用図記号 JIS Z8210](https://www.ecomo.or.jp/barrierfree/pictogram/picto_top2025.html) | **公式ピクトグラム** | **誰でも自由に使用可**。掲示物の第一候補。EPS/PNGで配布 |
| [いらすとや](https://www.irasutoya.com) | イラスト | **1制作物21点以上は有償** |
| [ソコスト](https://soco-st.com) | イラスト | 素材集への転用・AI学習は禁止 |
| [ICOOON MONO](https://icooon-mono.com) | アイコン | 再配布禁止 |
| [SILHOUETTE DESIGN](https://kage-design.com) | シルエット | 加工・色変更可 |
| [Pixabay](https://pixabay.com) | 写真・動画 | クレジット不要 |
| [写真AC](https://www.photo-ac.com) | 写真 | 無料登録が必要 |
| [Pexels](https://www.pexels.com/ja-jp/videos/) | 動画 | 商用可 |
| [Mixkit](https://mixkit.co) | 動画 | 全素材が商用可 |
| [魔王魂](https://maou.audio) | BGM・効果音 | 動画のBGMに |
| [DOVA-SYNDROME](https://dova-s.jp) | BGM | 動画のBGMに |

**ぱくたそは使いません。** 自動収集を明確に禁止しており（違約金 1点3万円/日・上限30万円）、
このアプリの用途と相性が悪いためです。

Canva は「Canva上で編集して使う」サービスなので、素材としての取り込みには向きません。

## アプリが自動で用意するもの（置かなくてよい）

| 素材 | 出どころ | ライセンス |
|---|---|---|
| アイコン・記号（駐輪禁止など） | Google Material Symbols | Apache-2.0 |
| 日本語フォント（極太見出し用） | Google Fonts / Noto Sans JP | SIL OFL |

どちらも自動取得が認められているので、初回に取得して `tools/assets/` に保存します。

## 出典を残す

どこから取った素材かを `SOURCES.md` に書き足しておくと、後で確認するときに困りません。
