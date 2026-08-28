# 同梱している素材のライセンス

このゲームは GitHub Pages で公開している（＝再配布にあたる）ので、
**再配布が明示的に許されているものだけ**を同梱する。

## 書体

| ファイル | 書体 | 作者 | ライセンス |
|---|---|---|---|
| `fonts/Orbitron-700.woff2` `fonts/Orbitron-900.woff2` | Orbitron | Matt McInerney | SIL Open Font License 1.1 |
| `fonts/ZenKakuGothicNew-500.woff2` `fonts/ZenKakuGothicNew-700.woff2` | Zen Kaku Gothic New | Yoshimichi Ohira | SIL Open Font License 1.1 |

SIL OFL 1.1 は **商用可・埋め込み可・改変可・再配布可**（フォント単体を売ることだけ禁止）。
どちらも Google Fonts から `tools/fetch-font.py` で取得している。
Google Fonts は API 経由での自動取得を認めている。

- OFL 全文: https://openfontlicense.org/
- Orbitron: https://fonts.google.com/specimen/Orbitron
- Zen Kaku Gothic New: https://fonts.google.com/specimen/Zen+Kaku+Gothic+New

**使う文字だけに絞ったサブセット**なので、収録字数は元のフォントより少ない
（OFL はサブセット化・改変を認めている）。

## 音

**音のファイルは1つも入っていない。** 効果音もBGMも WebAudio の合成音で、
`index.html` の中で作っている（＝持ち込んだ素材のライセンス問題が起きない）。

録音した素材に差し替えるときは、`assets/audio/` に置いて `index.html` の
`USE_FILES` を `true` にする。**そのとき入れてよいのは商用可かつ再配布可のものだけ**
（効果音ラボ・CC0 など）。クレジット表記が要る素材は、画面に表記欄を作らない限り使わない。

## 絵

画像ファイルは1枚も使っていない。惑星・ブラックホール・結晶・砲台はすべて
Canvas 2D で毎フレーム描いている。
