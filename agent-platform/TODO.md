# TODO — マルチプロダクション（agent-platform）

## 進行中

- [x] ディレクトリ構造・requirements.txt・.env.example の作成
- [x] core（設定・LLMルーティング・ジョブ文脈・パイプライン実行器）の骨組み
- [x] 全11部隊のエージェント初期コード（APIキー無しでも縮退モードで通る）
- [x] Streamlit UI（入力フォーム画面＋処理ログ画面＋成果物ダウンロード） port 8532
- [x] tests/（pytest）と `--doctor`（環境診断）

## 次にやること

- [x] 実キーでの疎通確認（claude CLI＝司令塔・企画・法務／Gemini＝調査・チェック・SNS・**画像**）
- [x] フル1本の実行確認（pptx / mp3×4 / mp4 2分13秒 まで実物を確認）
- [x] 費用方針を「全部無料」に確定（`AP_ALLOW_PAID=0`。画像生成とVeoを既定オフ）
- [x] 無料の代替を実装（実写真＋HTML作図／ケンバーンズ）
- [x] 講演スライドを .pptx で作り直し（4:3・面の型8種）＋フリー素材の自動補充（Openverse・キー不要）
- [ ] **出来た .pptx の見栄えを目視確認**（`output/test-deck-quality/slides/deck.pptx` 11枚）。
      機械での画像化は手段なし（LibreOffice未導入／PowerPointのAppleScript書き出しが無反応・原因未特定）
- [ ] OpenAI・Groq・ElevenLabs 経路は**未検証**（キーが無いため。コードは書いてある）
- [ ] 課金済み額の確認（Veoテスト$0.80＋生成画像十数枚）。AI Studio の請求画面で要確認
- [ ] 司令塔が遅い（MCP込みで4分）。道具の要否を部隊ごとに絞る
- [ ] LaMaのマスク自動生成（今は人の指定が必要）。物件写真の自動お掃除に必要
- [ ] Google Sheets MCP を足して「台帳の50物件を一括処理」を可能にする
- [ ] 動画に字幕を焼き込む（現状ナレーションのみ。音を出せない環境で内容が伝わらない）
- [ ] ppt_builder のデザインテンプレート（配色・フォント）を大京商事仕様に
- [ ] video_editor: 字幕焼き込み・BGM・トランジションの追加
- [ ] publisher: 実際のX/YouTube API投稿（現状は文面生成のみ。投稿は人間が最終確認する運用）

## 判断メモ（後任向け）

- Python 3.9.6（システム標準）で動くよう記述。`str | None` 等 PEP604 記法は使わない
- ffmpeg 未インストール → `imageio-ffmpeg` 同梱バイナリを使う。moviepy は v1/v2 両対応の互換シムあり
- 分類は「ツール」なので run.sh は `127.0.0.1` バインド（社内LAN共有しない）
