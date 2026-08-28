# 同梱物のライセンス

## 書体（assets/fonts/）

| ファイル | 書体 | ライセンス |
|---|---|---|
| `Orbitron-700.woff2` / `Orbitron-900.woff2` | Orbitron（Matt McInerney） | SIL Open Font License 1.1 |
| `ZenKakuGothicNew-500.woff2` / `ZenKakuGothicNew-900.woff2` | Zen Kaku Gothic New（Yoshimichi Ohira） | SIL Open Font License 1.1 |

**OFL 1.1 は 商用可・埋め込み可・改変可・再配布可**（フォント単体を有償で売ることだけ不可）。
このリポジトリは public で GitHub Pages から配信するので、再配布可であることが要る。

どちらも Google Fonts から `css2?...&text=` で取得している（**使う文字だけのサブセット**）。
取得は `tools/fetch-font.py`。**画面の文字を変えたら流し直すこと**（忘れると □ になる）。

## 音

**音のファイルは1つも同梱していない。** すべて WebAudio による合成音
（`index.html` の `sfx()` / `musicTick()`）。素材のライセンスを持ち込まずに済ませるため。

録音素材に差し替えるときは `assets/audio/` に置いて `USE_FILES = true` にする。
持ち込んでよいのは **商用可 かつ 再配布可**（効果音ラボ・CC0 など）のものだけ。
クレジット表記が要る素材は、アプリ内に表記欄を作らない限り使わない。
