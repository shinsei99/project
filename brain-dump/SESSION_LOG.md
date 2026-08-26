# brain-dump セッションログ

## 2026-08-26（メインPC）

### 完了したこと
- サブPCの iOS 録音修正（8/25）を **メインPCの常駐(3002)へ反映**した。
  `npm run build` → `launchctl kickstart -k gui/$(id -u)/com.shinsei.brain-dump` → HTTP 200。
  ビルド成果物 `.next/static/chunks/` に `wakeLock` が含まれることまで確認（＝新コードが配信されている）。

### 発生したエラーと解決策
- 症状: サブPCの引き継ぎ書に「brain-dump は**常駐していない**（launchd 未登録・Vercel 運用）ので
  `git pull` だけでよい」とあったが、**メインPCでは launchd に登録されている**
  （`com.shinsei.brain-dump`・`next start -p 3002 -H 0.0.0.0`）。
  → 原因: サブPCは常駐を持たない役割なので、サブPC側の観測では登録が無い（PCで状態が違う）。
  → 直し方: `next start` は**ビルド済みの `.next` を配信する**ので、pull だけでは反映されない。
  **`npm run build` を挟んでから kickstart する**までがワンセット。
  （Streamlit 常駐が「kickstart しないと古い import のまま」なのと同じ理由の Next.js 版）

### 次回への引き継ぎ事項・未解決の課題
- **3002 が `*:3002`＝社内LANに出ている**。brain-dump は分類上「ツール（社内共有なし）」で、
  CLAUDE.md のバインド規則ならツールは `127.0.0.1` のはず。plist が `-H 0.0.0.0` になっている。
  **落とすかどうかはオーナー判断**（引数を変えるので `kickstart -k` では反映されず、
  `bootout` → `bootstrap` が必要）。

## 2026-08-25（サブPC）

### 完了したこと
- iPhone Safari で音声入力が「1分くらいでエラー（録音が空）」になる件を調査し、`app/page.tsx` を修正
  - `rec.start(1000)` … timeslice を指定して1秒ごとに chunk を回収
  - `finishRecording()` で chunk 到着を最大3秒待ってから Blob 化（`cleanupStream()` を Blob 生成後へ移動）
  - 録音中だけ **Screen Wake Lock** を取得（iPhone の自動ロックでマイクが止まるのを防ぐ）
  - 音声トラックの `onended` を拾って自動停止 → そこまでの録音を文字起こしへ回す
  - エラー文言を「録音が空でした」→「録音を取り込めませんでした。録音中は画面を消さず…」に変更
- `npm run lint` / `npm run build` 通過。ログイン〜メイン画面を `./va.sh` で目視
- Chrome（`--use-fake-device-for-media-stream`）で録音〜文字起こしを通しで実行し、
  timeslice=1000・5秒で chunk 4個・停止後に最後の1個、を実測
- 調査で分かった事実を `README.md` に追記

### 発生したエラーと解決策
- 症状: iPhone Safari で1分ほど録音して停止 →「録音が空でした」。短い録音では成功する
  → 原因: ① iOS Safari は `ondataavailable` が `onstop` より後に届くことがあり、
    timeslice なしだと `onstop` 時点で chunk が 0 個 →`blob.size === 0`。
    ② iPhone の自動ロックで画面が消えるとマイクトラックが止まり録音が切れる
  → 直し方: timeslice で逐次回収＋chunk を待ってから Blob 化＋Wake Lock（上記）
- **サイズ超過・タイムアウトではないことを先に潰した**（憶測で直さないため）:
  59秒の音声は 250KB（data URL 334KB）で上限 3.5MB の1割、
  ローカル `/api/transcribe` の所要は 9秒で `maxDuration = 60` に収まる

### 次回への引き継ぎ事項・未解決の課題
- **本番（Vercel）へデプロイ済み**（2026-08-25・オーナー許可のうえ実施）。target=production・
  alias `brain-dump-sable-one.vercel.app`・HTTP 200・配信JSに新コードが入っていることまで確認
- **iPhone 実機で確認済み（2026-08-25・オーナー確認）。「いけてる」＝1分以上の録音が文字起こしされる。**
  この件の残タスクは無し。メインPCでやることは `git pull` だけ（常駐していないので再起動不要）
- Wake Lock は iOS 16.4+ のみ。それ以前の iOS では従来どおり画面ロックで切れるが、
  timeslice のおかげで**そこまでの録音は文字起こしされる**（全部消えることはなくなった）
