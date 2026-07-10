# launchd 登録キット（file-finder / owner-payout-tracker）

社内LAN常時起動（launchd）に **file-finder(8520)** と **owner-payout-tracker(8519)** を
追加するためのインストーラ。メインPC・サブPC 両方で同じものが使える。

## 使い方（メインPCでの引き継ぎ）

```bash
cd ~/           # リポジトリ（= $HOME）
git pull
bash ~/_launchd/install-launchd.sh
```

- `$HOME` を使うのでユーザー名に依存しない。
- 冪等（何度実行してもOK）。既存ロードは unload → load し直す。
- 初回は各アプリの `run.sh` が `.venv` を自動作成し `pip install -r requirements.txt`
  するため、ポートが上がるまで数十秒かかることがある。
- ログ: `~/Library/Logs/com.shinsei.<app>.{log,err.log}`

## 確認

```bash
launchctl list | grep -E "file-finder|owner-payout"
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8519/
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8520/
```

## 解除したいとき

```bash
launchctl unload ~/Library/LaunchAgents/com.shinsei.file-finder.plist
launchctl unload ~/Library/LaunchAgents/com.shinsei.owner-payout-tracker.plist
```

生成される plist は `~/Library/Library/LaunchAgents` ではなく
`~/Library/LaunchAgents/` に置かれる（git 管理外）。plist の実体は
このスクリプトが `$HOME` から絶対パスを埋めて生成する
（launchd は plist 内の環境変数を展開しないため、テンプレではなく生成方式）。
