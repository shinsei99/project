# SESSION_LOG.md — theta-viewer 作業ログ（PDCAのAct・引き継ぎ）

新しい項目は上に追記する（新しいものが上）。**上書きせず必ず追記。**
見出しには日付とどのPCで作業したかを必ず書く（`（メインPC）`/`（サブPC）`）。

---

## 2026-08-19（メインPC）

### 完了したこと
- **このファイルと `TODO.md` を新規作成し、`README.md` を実体のある内容に書き直した。**
  サブPCからの引き継ぎ依頼（直下 `TODO.md` の 3-b）への対応。
  それまで `README.md` は **Vite の雛形のまま**（THETA・パノラマの記述が0件）で、
  直下 `CLAUDE.md` が「このアプリの詳細はREADMEにある」と指しているのに中身が無い状態だった。
  `SESSION_LOG.md` と `TODO.md` は存在しなかった。
- READMEは**憶測ではなく実物のコードを読んで書いた**（下記はその際に確認した事実）。
  - 画面は HashRouter の4本（`/` 一覧 / `/admin` 作成 / `/property/:id` 閲覧 / `/edit/:id` 編集）
  - AIモデルは `onnx-community/Depth-Anything-V2-Small-ONNX`（奥行き）と
    `Xenova/swin2SR-classical-sr-x2-64`（超解像）。**どちらもブラウザ内推論**で、
    画像はサーバーへ送らない（`src/aiWorker.ts` の WebWorker）
  - 3D化は `THREE.SphereGeometry(10, 128, 64)` の頂点を深度で押し引きする方式
    （`src/PanoramaViewer.tsx`）
  - サーバー（`server/server.js`）は **DBを持たず、FTPで上げ下ろしするだけ**。
    物件情報の正典は公開先の `index.json` と `<id>/meta.json`

### 発生したエラーと解決策
- 特になし（ドキュメント作成のみでコードは触っていない）。

### 次回への引き継ぎ事項・未解決の課題
- **`src/firebase.ts` は Firebase を使っていない**（名前だけの名残）。`package.json` には
  `firebase` と `@supabase/supabase-js` が依存として残っているが、
  **実際に import しているか未確認**。使っていないなら外せるが、今回は触っていない。
- **FTP APIのポートは 8523 が正**（コードの `PORT = 8523`）。
  メモリ `project_theta_viewer.md` に **8522 と書かれた古い記述が残っている**ので、
  次に触るときに直す（別途 `project_theta_viewer_port_fix.md` が「8523が正」と訂正済み）。
- このアプリの**テストは無い**。UIを触ったら `./va.sh` で目視確認すること。
