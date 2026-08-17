# TODO — スクラップメモ（scrapmemo-petapeta）

## 進行中（2026-08-17）

- [x] スクラップ編集シートの改良（開いたとき先頭が出ない／ボタンを末尾へ）
- [x] 1.0.3 / build 7 で Archive 成功・commit f47056c を push（Web版もActionsで反映）
- [ ] **残: ユーザー実機** Organizer → Distribute App → App Store Connect でアップロード →
      ASCで新バージョン **1.0.3** を作成 → **ビルド7** を選択 → 審査提出
- [ ] 未確認: iOS実機・シミュレータでの表示（今回の確認はSafari 390×844のみ）。
      特にソフトキーボードが出た状態の見え方

## 分かっている課題（未着手）

- データがすべて localStorage（`snb6p` ほか）にJSON文字列で入っており、画像はdataURL。
  **約5MBの上限に当たると保存が丸ごと失敗する**。書き出し／取り込み（バックアップ）も無い
- タグ・分類が無く、ページが増えると探しづらい
- Web版（GitHub Pages）とiOS版でデータが行き来しない
