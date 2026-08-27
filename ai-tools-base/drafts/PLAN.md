# 在庫を書き切るための束ね計画（2026-08-26）

`drafts/NETA.md` の63本を、**記事として成立する単位**にまとめた表。
1項目=1記事にはしない（同じ原因の別アプリ版が並ぶと、読むほうが飽きる）。

- 〔不動産〕= 本体 + Zenn + note の3媒体　〔ツール〕〔メディア〕= 本体のみ
- 状態: ⬜未着手 / 📝原稿あり（3媒体ぶん揃った） / ✅公開済み
- **Zenn は毎日22:30に1本ずつ予約公開**（`./publish.sh zenn-schedule`）

| # | slug | NETA | 分類 | 状態 | 中身 |
|---|---|---|---|---|---|
| 1 | kana-name-matching | 1 | 不動産 | 📝 | 任意依存が無いと突合の一致率だけ静かに落ちる |
| 2 | stale-data-star-filename | 53 | 不動産 | 📝 | ファイル名の★で古い表を読み続ける（小説10話） |
| 3 | deploy-not-reflected | 9,10,11,14 | 不動産 | 📝 | 「直したのに反映されない」4パターン |
| 4 | line-free-quota-silent | 4 | 不動産 | 📝 | 受付だけ届いて回答が消える（無料枠切れ） |
| 5 | safe-default-on-unreadable | 3 | 不動産 | 📝 | 読めないときの既定値を安全側へ |
| 6 | exit-code-zero-partial | 5 | 不動産 | 📝 | 終了コード0で中断していた |
| 7 | default-bind-0000 | 7,8 | 不動産 | 📝 | 指定しないとLANに出る（Streamlit / Next.js） |
| 8 | launchd-cannot-read-cloud | 12,13 | 不動産 | 📝 | 常駐がクラウド同期フォルダを読めない／TCCの責任プロセス |
| 9 | office-report-layout | 18,19,20 | 不動産 | 📝 | Excelが修復扱い・Wordの罫線・末尾の□ |
| 10 | excel-image-aspect | 17,22,23 | 不動産 | 📝 | 写真が縦に潰れる／直さないと決めたバグ／表示の丸め |
| 11 | form-field-detection | 24,26,28,29,30 | 不動産 | 📝 | 公式書式の入力欄をどう当てるか |
| 12 | leftover-in-output | 25,27 | 不動産 | 📝 | 出力に前の案件が残る（雛形／代替処理）※12と13を束ねた |
| 14 | legacy-office-convert | 31,32,33 | 不動産 | 📝 | 旧 .doc/.xls と、向きの自動補正 |
| 15 | model-lifetime | 35,36,37,38 | 不動産 | 📝 | モデルとSDKの寿命・思考トークン・タイムアウト |
| 16 | generated-text-leaks | 39,40,41 | 不動産 | 📝 | 生成物に混じる内部記号・設定ファイルのコメント |
| 17 | normalize-japanese-data | 48,49,50 | 不動産 | 📝 | ハイフン7種・全角半角・NFD（※再編：正規化に集約） |
| 18 | japanese-no-word-boundary | 51,52,57 | 不動産 | 📝 | 語の区切りが無いので、市区町村名と法令名が切れない |
| 19 | api-wrong-endpoint | 54,55,56 | 不動産 | 📝 | キーはあるのに常に空／%の二重付与 |
| 21 | sqlite-transaction | 60,61,64 | 不動産 | 📝 | executescript の暗黙COMMIT／時刻だけでは順序が決まらない（小説12話） |
| 23 | chrome-download-limit | 47 | 不動産 | 📝 | 自動ダウンロードの制限は自動では回避しない |
| 24 | env-differs-in-production | 2,6 | 不動産 | 📝 | 本番だけ違うものが動く（固定パス／常駐のPython） |
| 25 | a4-one-page-layout | 21 | 不動産 | 📝 | 帳票をA4一枚に収め続ける（🔍コードから） |
| 26 | ios-capacitor-traps | 43,44,45,46 | ツール | 📝 | キーボードでWebViewが縮む／sync漏れ／SPM／ビルド番号 |
| 27 | streamlit-execution-model | 62,63,65,66 | ツール | 📝 | 実行モデルで踏む4つ（※28を統合） |
| 29 | external-data-quirks | 58,59 | ツール | 📝 | GETは200で空／平均が空で最安だけ入る |
| 30 | media-ops | 15,16 | メディア | 📝 | Vercelは手動・--scope／Zennの投稿上限は黙って落ちる |

**進め方**: 上から順ではなく、章（原因の系統）がばらけるように選ぶ。
書いたら NETA.md の該当行を消し、この表の状態を更新する。
