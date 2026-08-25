# brain-dump セッションログ

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
- **本番（Vercel）へは未デプロイ。** `npx vercel --prod` はオーナーの許可が要るため保留
- **iPhone 実機での確認が未了。** この不具合は iOS Safari 固有で Mac の Chrome では再現しないため、
  デプロイ後に実機で「1分以上の録音 → 文字起こしされる」ことを確かめる必要がある
- Wake Lock は iOS 16.4+ のみ。それ以前の iOS では従来どおり画面ロックで切れるが、
  timeslice のおかげで**そこまでの録音は文字起こしされる**（全部消えることはなくなった）
