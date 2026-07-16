# madori-tracer

- `app.py` ほか: StreamlitメインアプリのAI間取りトレーサー（port 8511、launchd常時起動: com.shinsei.madori-tracer）
- `editor/`: 手動間取りエディタ（Vite + React + TypeScript、port 5175、launchd常時起動: com.shinsei.madori-tracer-editor）。パーツ配置・トレース画像の下敷き編集用。`npm run build`後に`node_modules/vite/bin/vite.js preview`でdistを配信する構成のため、editor側のコードを変更したら`npm run build`→`launchctl kickstart -k gui/$(id -u)/com.shinsei.madori-tracer-editor`が必要（devサーバーの自動リロードは常時起動プロセスには反映されない）
