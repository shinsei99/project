# mcp.json — 各部隊に配るMCPサーバー

`claude` CLI に `--mcp-config mcp.json` で渡している。**ここに1行足すだけで全部隊の道具が増える**
（個別のAPI実装が要らない）のが、この仕組みを使う理由。

**注意: `mcp.json` にコメントキー（`_comment` など）を書くと
`Invalid MCP configuration: MCP config is not a valid JSON` で起動に失敗する。**
説明はこのファイルに書くこと。

## いま入れているもの

| サーバー | 何ができるか | 認証 |
|---|---|---|
| `playwright` | ブラウザ操作。JSで描画されるページや、操作しないと出ない情報も読める（WebFetchより強い） | 不要 |
| `filesystem` | `output/` の読み書き。範囲をそこだけに限定している（他のフォルダは触らせない） | 不要 |

## 足すと効きそうなもの（未接続）

| サーバー | 用途 | 必要なもの |
|---|---|---|
| Google Drive / Sheets | 物件台帳を読んで一括処理、成果物の共有 | OAuth |
| Slack / Chatwork | 完了通知・承認フロー | トークン |
| Dropbox | 社内共有フォルダへ自動保存（既存の運用に直結） | トークン |
| Notion | 議事録・ナレッジの参照 | トークン |

## 切り方

- 全部止める: `.env` で `AP_MCP=off`
- 一部だけ許可: `.env` で `AP_MCP_TOOLS=mcp__playwright`
- 別ファイルを使う: `.env` で `AP_MCP_CONFIG=別の.json`

`npx` が毎回起動するぶん、MCPを有効にすると1呼び出しあたり数秒遅くなる。
使わないときは `AP_MCP=off` が速い。
