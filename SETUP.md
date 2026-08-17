# SETUP.md — このPCで全アプリを触れるようにする

**gitで来るのはコードだけ。** 依存関係（`.venv` / `node_modules`）と機密（`.env` 等）は
来ないので、PCごとに1回用意する。その手順と、PCをまたぐときの注意をここにまとめる。

---

## 1. いまの状態を見る

```bash
python3 dev-doctor.py            # 全アプリ
python3 dev-doctor.py 不動産      # カテゴリで絞る（不動産 / ツール / ゲーム）
python3 dev-doctor.py baikai     # 名前の一部で絞る
```

出るのは4点。

| 列 | 意味 |
|---|---|
| 依存 | `.venv` / `node_modules` があるか。**無ければ動かない** |
| 機密 | `.env` 等が要るアプリか、あるか。`**要**` は**メインPCから運ぶ必要がある** |
| 待受 | `run.sh` のバインド先とポート |
| 稼働 | 実際に待ち受けているか（`*` は**LAN全体に公開**、`127.0.0.1` はこのPCのみ） |

**ツール・ゲーム分類が `0.0.0.0` で待ち受けていたら ⚠️ が出る。**
これらは社内共有しない決まりなので、出たら `run.sh` を直す
（Streamlitは `--server.address` を省略すると既定が `0.0.0.0`＝LAN公開。詳細はルート CLAUDE.md）。

## 2. 足りない依存を作る

```bash
./dev-setup.sh baikai-generator      # 1本だけ
./dev-setup.sh --all                 # 不足している全部（Python仮想環境の作成が中心。時間がかかる）
./dev-setup.sh --all --dry-run       # 何をするかだけ見る
```

- 1本が失敗しても止まらず、最後にまとめて報告する
- ログは `logs/setup-<アプリ>.log`
- **`chatwork-ai-manager` だけ venv を作らない。** venv の Python から `claude` を呼ぶと
  SIGSEGV で落ちるため、`/usr/bin/python3` 固定。依存は `.deps/` に入れて `PYTHONPATH` で読む

### 見つかった不具合（2026-08-16 の整備で判明）

依存を作り直したことで、**それまで誰も環境を作れなかった／静かに劣化していた**箇所が2つ出た。
同種のものが他にもある可能性があるので、触るアプリでは一度 `import` が通るか確かめること。

| アプリ | 症状 | 原因 | 直し方 |
|---|---|---|---|
| `madori-tracer` | `pip install -r requirements.txt` が必ず失敗する | `streamlit-cropper>=0.7` を要求しているが、**PyPIには 0.3.1 までしか存在しない** | 実在するバージョンへ修正（済） |
| `payment-reconciler` | 入金の突合率が下がるが、**エラーは出ない** | `pykakasi`（漢字→カナ変換）が try/except の暗黙フォールバックで、`requirements.txt` に入っていなかった | requirements に追加＋**未導入なら画面に警告を出す**ようにした（済） |

`payment-reconciler` の方は `photo-inpainter` と同じ形（**入れ忘れた依存が静かに代替経路へ落ちる**）。
optional import を書くときは、**落ちたことが見えるようにする**こと。

## 3. 起動する

```bash
cd <アプリ> && ./run.sh          # ポートは run.sh に書いてある（一覧はルート CLAUDE.md）
```

静的HTMLのアプリ（gyomu-manual / ゲーム類）はブラウザで直接開く。

---

## 4. ⚠️ PCをまたぐときに守ること

### (1) `chatwork-ai-manager` の **本体はメインPCのみ**（2026-08-16 確認）

**メインPCだけで動かすのは「本体」＝ worker / LINE webhook / ngrok の3つ。**
2台で動かすと **Chatwork・LINEへ二重返信**し、ngrokの固定ドメインを奪い合う。
DBも双方向マージできない。

**管理画面（8540）はサブPCで起動してよい。** 外部へ投稿しないため。

```bash
cd chatwork-ai-manager && ./run.sh      # 管理画面だけ。run_worker.sh / run_ngrok.sh は叩かない
```

- `dev-doctor.py` は、本体プロセスがこのPCで動いていたら ⚠️ を出す
- 本体を移すときは、**先に旧PC側で**
  `launchctl unload ~/Library/LaunchAgents/com.shinsei.chatwork-ai-manager*.plist` してから、
  `handoff_export.sh` → Dropbox → `handoff_import.sh` でDBごと運ぶ
- このアプリの機密は `secrets-sync.sh` では扱わない（専用スクリプトを使う）

### (2) 社内LAN公開の常駐は、原則メインPCだけ

社内の共有ショートカットはメインPC（192.168.1.105）を指している。
サブPCで同じアプリを launchd 常駐させると、**同じ内容が2つのIPでLANに出る**。
個人情報を含むアプリ（オーナー送金・ファイル棚卸しなど）は特に注意。

```bash
launchctl list | grep shinsei                                     # このPCの常駐を確認
launchctl unload ~/Library/LaunchAgents/com.shinsei.<アプリ>.plist  # 止める
```

### (3) iOSアプリはビルド番号を必ず上げる

再アップロード時に `CURRENT_PROJECT_VERSION` を +1 しないと、**古いビルドがそのまま審査を通る**。
`./ios-build-guard.sh <app-folder>` で衝突を確認してから Archive する（詳細はルート CLAUDE.md）。

---

## 5. メインPCから機密をもらう（Dropbox経由）

**コードはgit、機密は個人Dropbox。** 運ぶ対象は `secrets-manifest.txt`（パスだけを書く）。

```bash
./secrets-sync.sh check      # このPCに何が無いかを見る（両方のPCで使える）
./secrets-sync.sh export     # 持っている側（メインPC）で実行 → Dropbox-個人へ
./secrets-sync.sh import     # 欲しい側（サブPC）で実行。既存は上書きしない
./secrets-sync.sh import --force   # 上書きする
```

- 置き場は `~/Library/CloudStorage/Dropbox-個人/apps-secrets-handoff/`。
  **会社共有のDropboxには置かない**（他スタッフから見える）
- **新しく `.env` を作ったら `secrets-manifest.txt` に1行追記する。** 載っていないものは運ばれない
- `chatwork-ai-manager` は対象外。専用の `handoff_export.sh` / `handoff_import.sh` を使う

**2026-08-16 時点で、このサブPCに不足しているのは `digital-shosai/.env.local`（Supabase）だけ。**

参考: 揃っていることを確認済みのもの

- `agent-platform` … `config/` `knowledge/` `.env`（Geminiキー入り）
- `chatwork-ai-manager` … `.streamlit/secrets.toml` / `data/app.db`（170MB）
- `kaitori-dm-maker/senders.json` / `flyer-creator/.stats_key` / `psa-collection/data/collection.csv`
- Dropbox（個人・大京商事）と Google Drive はマウント済み（`~/Library/CloudStorage`）
- `psa-collection/data/orders.json` は無いが、**ログイン済みSafariから再取得できる**（`./update_orders.sh`）

---

## 6. アプリ側の作法（全アプリ共通）

- 着手前に `<アプリ>/TODO.md` に1行書く。区切りで `<アプリ>/SESSION_LOG.md` の**先頭**へ追記
- 調べて分かった事実（APIの仕様・はまりどころ）は `<アプリ>/README.md` に残す
- 憶測を事実として書かない。数値は測った値を書く
- 詳細はルート `CLAUDE.md` の「作業ルール（PDCA・引き継ぎ）」
