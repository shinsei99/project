# 引き継ぎ手順（メインPCへ）

2026-08-14 作成。**コードは git、データは Dropbox** の二本立てで運ぶ。

## なぜ分けるのか

| | サイズ | 置き場 | 理由 |
|---|---|---|---|
| コード・文書 | 480KB | GitHub（このリポジトリ） | 軽い。以後の同期も git で済む |
| `data/` | 4.3GB | Dropbox（個人） | 重すぎて git に載らない。**個人情報も含む** |

`data/` には**カード画像31,520枚**と `cards.db`（38MB）が入っている。
`.gitignore` で追跡対象から外してあるので、**間違って git に入ることはない**。

## 受け取り側（メインPC）の手順

### 1. コードを取る

```bash
cd ~ && git pull origin main
```

`pokecard-dex/` に .py と .md が入る（38ファイル）。

### 2. データを Dropbox から展開する

Dropbox の `pokecard-dex-handoff/` に置いてある。同期が終わってから:

```bash
cd ~/pokecard-dex
tar xf ~/Library/CloudStorage/Dropbox-個人/pokecard-dex-handoff/pokecard-dex-data.tar
```

`data/` ができる。**約3.8GB**（展開後）。

### 3. 再生成できるものを作る

転送量を減らすため、**次の2つは送っていない**。手元で作る。

```bash
# Python環境（303MB）
python3 -m venv .venv && .venv/bin/pip install -q -r requirements.txt

# 一覧用サムネイル（510MB）。myca_large から数秒で作れる
.venv/bin/python make_thumbs.py
```

### 4. 動作を確かめる

```bash
.venv/bin/python check_dex.py | head -8      # 画像欠落 0枚 になるはず
./run.sh                                      # http://127.0.0.1:8531
```

`check_dex.py` で「画像欠落 0枚」なら成功。数が合わないときは
`.venv/bin/python build_dex.py` で組み直す（DBの `dex` テーブルを作り直すだけで、
取得済みの画像には触らない）。

## 引き継ぐ状態（2026-08-14 時点）

**画像は 100%（31,520 / 31,520）収録済み。** ただし内訳に注意。

| 区分 | 枚数 | 引き方 |
|---|---|---|
| 出所がはっきりしている | 31,500 | — |
| **推定**（トロフィーカードの大会が確定していない） | 14 | `SELECT * FROM trophy_guess` |
| **参考画像＝実物ではない** | 4 | `SELECT * FROM placeholder_images` |
| 透かし入り（晴れる屋2） | 2 | `SELECT dex_key FROM extra_images WHERE source='hareruya2'` |
| 受賞者の顔と実名をぼかした複製 | 5 | `data/pokumon_masked/` |

続きの作業は `TODO.md`、経緯は `SESSION_LOG.md`、取得元ごとの手順は
`README.md` にある。**同じ調査を繰り返さないよう、空振りした先も記録してある。**

## 注意

- **`data/` を git に入れないこと。** 個人情報（受賞者の顔写真・実名が印刷された
  カード画像）を含む。`.gitignore` で除外済み
- コードと文書からは**受賞者の実名を伏せ字にしてある**（`〈受賞者名〉`）。
  リポジトリが公開のため。画像側はぼかし処理で対応している
- port 8531・`127.0.0.1` バインド（自分専用。社内LANに出さない）
- launchd 未登録
