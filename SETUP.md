# SETUP.md — このPCで全アプリを触れるようにする

**環境再現の入口はこのファイル1本。** gitで来るのはコードだけで、依存関係
（`.venv` / `node_modules`）と機密（`.env` 等）は来ないので、PCごとに1回用意する。

## 「同じ環境」の定義（2台で揃えるもの・2026-08-17決定）

**commitが同じだけでは同じ環境ではない。** 次の全部が揃って初めて「開発できる同一環境」とする。

| 揃えるもの | 基準 | 揃っているか見る方法 |
|---|---|---|
| ソースコード | `origin/main` | `./dev-doctor.py --sync --fetch` |
| Python | `.python-version`（現在 **3.9.6** = macOSの `/usr/bin/python3`） | 同上（実際の版と照合する） |
| Node.js | `.nvmrc`（現在 **26.3.1**） | 同上 |
| 依存関係 | 各アプリの `requirements.txt` / `package-lock.json`（**lockを優先。勝手に上げない**） | `./dev-doctor.py` の「依存」列 |
| 機密・データ | `secrets-manifest.txt` に載っているパス（**値はgitに入れない**） | `./dev-doctor.py --sync` の「機密」 |
| 自動起動 | **サブPCは常駐ゼロ**（メインPCだけが常駐と社内LAN共有を持つ） | `./dev-doctor.py --sync` の「自動起動」 |

`.python-version` / `.nvmrc` は **pyenv / nvm が無い環境では自動切替をしない**（宣言と照合用）。
Python 3.9 は2025年10月でEOLだが、31本のvenv全部が3.9.6なので**揃えることを優先して現状値で固定**した。
上げるときは31本の作り直しとセットになる。

---

## 1. いまの状態を見る

```bash
python3 dev-doctor.py                  # 全アプリ（依存・機密・待受・稼働）
python3 dev-doctor.py 不動産            # カテゴリで絞る（不動産 / ツール / ゲーム）
python3 dev-doctor.py baikai           # 名前の一部で絞る
python3 dev-doctor.py --sync --fetch   # ★2台の差分とコミット漏れの検知（作業の終わりに必ず）
```

`--sync` は **Git（未コミット・未追跡・stash・push漏れ・ローカルだけのブランチ・
`.gitignore` の許可行が無くて git に入っていないソース）／バージョン照合／機密の不足／
自動起動の状態** を見て、WARNING を並べる。**勝手に直さない**ので、出た内容は人が判断する。

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
launchctl list | grep shinsei                                      # このPCの常駐を確認
launchctl unload ~/Library/LaunchAgents/com.shinsei.<アプリ>.plist   # いま止める
launchctl disable "gui/$(id -u)/com.shinsei.<アプリ>"                # ★再ログインでも復活させない
launchctl print-disabled "gui/$(id -u)" | grep shinsei             # 無効化されたか確認
```

**`unload` だけでは足りない。** `~/Library/LaunchAgents/` に plist が残っていると
**次のログインで自動的に起動する**。サブPCでは `disable` までやる（plistは消さずに残す。
将来このPCを主機にするときは `launchctl enable` で戻せる）。
2026-08-17 に file-finder(8520) と owner-payout-tracker(8519) を disable 済み＝**サブPCの常駐は0本**。

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

**2026-08-17 実測: `secrets-manifest.txt` に載っている機密は全件そろっている（不足0件）。**

> `digital-shosai/.env.local`（Supabase）を長く「不足」として扱っていたが、**そもそも要らなかった**。
> このアプリは**完全オンデバイス版**（pdf.js＋IndexedDB・`output: "export"`）に作り替えられており、
> コード内に `process.env` の参照が**1つも無い**。`.env.local.example` が旧設計の名残として
> 残っていたため、点検ツールが「exampleがあるのに実体が無い」と誤検知していた。
> exampleを削除し、manifestからも外した（`npm run build` が通ることを実測で確認）。

> ⚠️ `secrets-sync.sh export` は **メインPCでは使えなかった**（道具自体が
> `.gitignore` の許可行漏れでコミットされておらず、メインPCに存在しなかった）。
> 2026-08-17 は Dropbox に手で並べて `rsync --ignore-existing` で運んだ。許可行は追加済みなので、
> 次回からは `export` / `import` が両PCで使える。
>
> **gitに乗らない「PC側の設定」も運搬対象に含める。** 例: MCPサーバーの設定
> （ユーザースコープは `~/.claude.json` の `mcpServers`）。2026-08-17 にメインPCへ追加された
> `VISUAL_AGENT` がサブPCに無い、という取りこぼしが実際に起きた。

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
