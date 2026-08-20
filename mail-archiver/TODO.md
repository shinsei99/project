# TODO — メールアーカイバ（mail-archiver）

## 進行中・次にやること

- [ ] **本番アカウント（shin@daikyocorp.co.jp）で初回の取り込みを試す** … 要オーナー確認。
      `--since-days 7 --limit 20` の小さい範囲から。実サーバーへの接続はまだ一度も行っていない
- [ ] 初回取り込みの実測を残す（何通で何分・何MB か。README に数値で書く）
- [ ] `restore.py`（`.eml` を IMAP APPEND で戻す）… 削除を実運用する前に用意したい
- [ ] メインPCへ渡すか決める（常駐させるなら launchd 登録・ポート8535。サブPCでは常駐させない）

## 完了

- [x] DB設計（accounts/folders/messages/attachments/delete_log/FTS5 trigram）
- [x] 取り込み（`sync.py --sync`）… 原本 .eml＋添付＋SHA256、`synced_at` を記録
- [x] サーバー側削除（`--delete` / `--yes`）… 14日ルール＋5つの照合＋UID EXPUNGE
- [x] 閲覧UI（`app.py` / port 8535 / 127.0.0.1）
- [x] `smoke_test.py`（偽IMAPサーバーで30項目。本物には繋がない）

## 決めたこと（蒸し返さない）

- **画面からサーバーのメールは消せない。** 取り違えて押す事故を無くすため、削除はCLIだけ。
- **削除は既定で無効**（`.env` の `ARCHIVE_DELETE_ENABLED=0`）。有効にしても `--yes` が要る。
- **未読・フラグ付き・ゴミ箱は消さない**（オプションで解除はできる）。
