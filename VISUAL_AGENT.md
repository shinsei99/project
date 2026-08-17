# 共通 Visual Agent（Claude Code がブラウザを見て操作する仕組み）

**1つの定義を2つの入口で共有する。** ブラウザ操作の仕組みを常駐AI専用に作らない、が方針。

```
LINE / Chatwork → AI業務マネージャー → Claude Code ┐
                                                   ├→ 共通Visual Agent（~/.mcp.json）
ターミナル → Claude Code ─────────────────────────┘        ↓
                                              Playwright MCP → Chrome（headless）
```

## 唯一の定義ファイル

`~/.mcp.json`（＝ `/Users/apple/.mcp.json`）。**ここ以外にブラウザ操作の設定を作らないこと。**

```json
{ "mcpServers": { "playwright": {
    "command": "npx",
    "args": ["-y", "@playwright/mcp@0.0.79", "--browser", "chrome", "--isolated", "--headless"] } } }
```

- `--browser chrome` … このMacに入っている Google Chrome を使う（追加のブラウザを落とさない）。
- `--isolated` … 毎回まっさらなプロファイル。**普段使いのChromeのCookie・履歴・ログイン状態には触れない。**
- `--headless` … 画面に窓を出さない。常駐workerが日中に動いても作業の邪魔をしない。
  実際の描画結果は `browser_take_screenshot` で画像として確認できる（headlessでも見た目は分かる）。
  画面に出して目で追いたいときは `--headless` を外す。

依存は `npx` が都度取得する（初回のみDL・以降キャッシュ。**追加インストール不要・APIキー不要・無料**）。

## 使える操作

`mcp__playwright__browser_*` … navigate / click / type / fill_form / select_option / hover /
press_key / snapshot（アクセシビリティツリー）/ take_screenshot / console_messages /
network_requests / resize / tabs / evaluate / wait_for / file_upload / handle_dialog。

## 入口A: ターミナルの Claude Code

`~` で起動すれば**自動で有効**（`~/.mcp.json` はプロジェクトスコープの設定として読まれる。
初回の承認は `~/.claude.json` の `enabledMcpjsonServers` に登録済みなので聞かれない）。

```bash
cd ~ && claude          # ← これだけでブラウザ操作が使える
```

別のフォルダで作業していて同じ能力が欲しいときは、設定ファイルを明示する:

```bash
claude --mcp-config ~/.mcp.json          # どのcwdでも共通Visual Agentが付く
# 毎回書くのが面倒なら ~/.zshrc に:  alias cv='claude --mcp-config ~/.mcp.json'
```

確認のしかた（セッション内で）: `/mcp` … playwright が connected なら使える。

## 入口B: AI業務マネージャー（LINE / Chatwork）から

`chatwork-ai-manager/services/claude_client.py` の `run_dev_agent()` が
`--mcp-config ~/.mcp.json --strict-mcp-config` を付けて claude を起動する。
＝ **ターミナルと同じファイル・同じMCP・同じChrome**を使う。切替設定は
管理画面「システム設定」の `dev_mcp_config`（既定 `/Users/apple/.mcp.json`）。

## 業務QA側には付けていない（意図的）

社内Q&A・TODO抽出・定時処理の `run_agent()` は `--strict-mcp-config` を付けて
**MCPを一切読まない**ままにしてある。ブラウザ道具は業務回答に不要で、
毎回のツール定義がコンテキストと定額枠を食うため。Visual Agent は開発タスクだけに載せる。

## つまずいたとき

| 症状 | 原因 / 対処 |
|---|---|
| `/mcp` に playwright が出ない | cwd が `~` 以外。`claude --mcp-config ~/.mcp.json` で起動する |
| 初回だけ異常に遅い | `npx` がパッケージを取得している（1回だけ。以降キャッシュ） |
| `browser_*` が「ページが無い」と言う | 先に `browser_navigate` する。`--isolated` なのでセッションは毎回新規 |
| ログインが必要なサイトを見たい | `--isolated` では毎回ログインが要る。フォーム入力で都度ログインするか、この用途だけ `--isolated` を外す |
| 画面を目で見たい | `--headless` を外す（Chromeの窓が開く）。常駐AI経由でも窓が出るので日中は注意 |

## 検証済み（2026-08-17）

`claude -p` のサブプロセスから、ローカルページを開く → 入力欄に文字を入れる → ボタンを押す →
DOMの変化を確認 → スクリーンショット保存、まで実際に成功（所要66秒）。
つまり**人が横で操作しなくても、AIだけでブラウザ検証が回る**ことを実機で確認済み。
