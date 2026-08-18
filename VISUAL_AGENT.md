# 共通 Visual Agent — Claude Code がブラウザを見て、操作して、UIを確かめる

**画面を見ずに「直りました」と言わないための道具。** 2台のPCが別々に作った2つの実装を
2026-08-18 に統合し、**1つの仕組み・2つの入口**にした。設定もコードも git に入っているので、
メインPC・サブPCのどちらでも `git pull` だけで同じものが使える。

```
                       ┌── 入口A: 会話の中（MCP）      … mcp__playwright__browser_*
Claude Code ───────────┤
                       └── 入口B: シェル（./va.sh）    … visual_agent.py
                                    ↓ どちらも
                          Google Chrome（headless・専用プロファイル）
```

## どちらを使うか

| | 入口A（MCP） | 入口B（`./va.sh`） |
|---|---|---|
| 呼び方 | 会話の中でそのまま（ツールとして見える） | `./va.sh <コマンド>` |
| 得意 | 対話しながら押す・入れる・読む | **UI崩れの機械検出 / レスポンシブ比較 / スクリプト・自動検証** |
| 記録 | そのセッション中 | **起動時からの Console・Network を取りこぼさず蓄積** |
| 要るもの | Node 18+（`npx` が都度取得） | Playwright(Python)（下記の順に自動で探す） |
| 使う場面 | ふつうの開発中。AI業務マネージャーの開発エージェント | `dev-doctor.py --verify`、まとめて撮る、CIっぽい検証 |

**迷ったら入口A。** 「崩れていないか機械で確かめたい」「3幅で撮って比べたい」ときだけ入口B。
どちらも**同じ Google Chrome を headless で開く**ので、見えるものは食い違わない。

## 入口A: MCP（会話の中）

定義は `~/.mcp.json` の**1ファイルだけ**。ここ以外にブラウザ操作の設定を作らない。

```json
{ "mcpServers": { "playwright": {
    "command": "npx",
    "args": ["-y", "@playwright/mcp@0.0.79", "--browser", "chrome", "--isolated", "--headless"] } } }
```

- `--browser chrome` … このMacの Google Chrome を使う（ブラウザを二重に落とさない）
- `--isolated` … 毎回まっさらなプロファイル。**普段使いのChromeのCookie・履歴・ログインに触れない**
- `--headless` … 窓を出さない。常駐workerが日中に動いても邪魔しない。
  見た目は `browser_take_screenshot` の画像で確認できる。目で追いたいときは外す

使える操作: `navigate / click / type / fill_form / select_option / hover / press_key /
snapshot（アクセシビリティツリー）/ take_screenshot / console_messages / network_requests /
resize / tabs / evaluate / wait_for / file_upload / handle_dialog`。

```bash
cd ~ && claude                       # ~ で起動すれば自動で有効
claude --mcp-config ~/.mcp.json      # 別フォルダで作業していて同じ能力が欲しいとき
```

セッション内の確認は `/mcp`（playwright が connected なら使える）。

**AI業務マネージャー（LINE / Chatwork）からも同じファイルを読む。**
`chatwork-ai-manager/services/claude_client.py` の `run_dev_agent()` が
`--mcp-config ~/.mcp.json --strict-mcp-config` を付けて起動する（管理画面「システム設定」の
`dev_mcp_config` で切替可）。**業務QA側（社内Q&A・TODO抽出・定時処理）には意図的に付けていない**
——ブラウザ道具は業務回答に不要で、ツール定義が毎回コンテキストと定額枠を食うため。

## 入口B: `./va.sh`（シェル）

```bash
./va.sh start [--headed] [--width 1440] [--height 900]   # 立ち上げて常駐
./va.sh goto localhost:3004        ./va.sh click "text=ツール比較"   ./va.sh fill "#q" 検索語
./va.sh shot [名前] [--full]        # 撮る → 出た .png を Read すると中身が見える
./va.sh check                      # UI崩れの機械検出（はみ出し・重なり・小さすぎる文字/ボタン）
./va.sh responsive <url>           # 390 / 768 / 1440 幅で撮って比べる
./va.sh console --errors           ./va.sh network --failed
./va.sh dom / a11y / text / eval <js> / upload / press / scroll / size / status / stop
```

- 実体は `visual_agent.py`。全コマンドと限界は `./va.sh --help`
- **Playwright(Python) は次の順で探す**（特定アプリの `.venv` に依存しない）:
  `VA_PYTHON` → `agent-platform/.venv` → `.va-venv` → `python3`
- **ブラウザは入口Aと同じ Google Chrome**（`channel=chrome`）。無いPCでは同梱 Chromium に
  自動で切り替え、起動メッセージにそう出る。`VA_BROWSER=chromium` で明示指定も可
- 無いPCでの入れ方:
  `python3 -m venv .va-venv && .va-venv/bin/pip install playwright && .va-venv/bin/playwright install chromium`
- 撮った画像・ログは `.see/`（**gitignore**。個人情報が写り得るのでコミットしない）

## 共通の決まり

- **パスワードは入力しない。** ログインが要る画面は人が入る。ログイン済みの実ブラウザで
  見たいときは Chrome拡張（Claude in Chrome）のほう
- 開くのは**専用プロファイル**（入口A=`--isolated` / 入口B=`.see/profile-<ブラウザ>`）。
  普段のログイン状態は無い
- Mac の画面そのものや `.pptx` / `.pdf` の見た目は `./see.sh screen` / `./see.sh file <ファイル>`

## 動くかどうかの確認（引き継ぎ時・調子が悪いとき）

```bash
./visual-agent-check.sh            # 入口A・Bの両方を点検し、最後に実際に操作させて確かめる
./visual-agent-check.sh --mcp      # 入口Aだけ    ./visual-agent-check.sh --va  # 入口Bだけ
```

## つまずいたとき

| 症状 | 原因 / 対処 |
|---|---|
| `/mcp` に playwright が出ない | cwd が `~` 以外。`claude --mcp-config ~/.mcp.json` で起動する |
| 初回だけ異常に遅い | `npx` がパッケージを取得している（1回だけ。以降キャッシュ） |
| `browser_*` が「ページが無い」と言う | 先に `browser_navigate` する。`--isolated` なのでセッションは毎回新規 |
| `./va.sh` が「Playwright が見つからない」 | 上の入れ方で `.va-venv` を作る。`VA_PYTHON` で明示も可 |
| `./va.sh start` が chromium と出る | Google Chrome が無いPC。動作に支障はないが、見た目を厳密に合わせるなら Chrome を入れる |
| ログインが必要なサイトを見たい | 毎回ログインが要る。フォーム入力で都度入るか、この用途だけ `--isolated` を外す |
| 画面を目で見たい | 入口A: `--headless` を外す／入口B: `./va.sh start --headed` |

## 検証済み（実測）

- 2026-08-17（メインPC）: `claude -p` のサブプロセスから、ページを開く → 入力 → ボタンを押す →
  DOMの変化を確認 → スクショ保存まで成功（66秒）。**人が横にいなくてもAIだけで回る**
- 2026-08-18（メインPC）: 統合後の `./va.sh` を Chrome / Chromium / `VA_PYTHON` 明示の3経路で実行し、
  `goto` → `shot` → `check` → `console --errors` まで成功（業務マニュアル 8521 で確認）
