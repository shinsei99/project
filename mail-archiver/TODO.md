# TODO — メールアーカイバ（mail-archiver）

## 進行中・次にやること

- [ ] **iCloud の App用パスワードを発行して、IMAP経由の取り込みを試す**（このPCのMail.appは
      iCloud 1本のみ。`.env.mail-archiver` は用意済み・削除は無効のまま）。
      `security add-generic-password -s mail-archiver -a <自分のiCloudアドレス> -w` で入れる
- [ ] 本番アカウント（shin@daikyocorp.co.jp・メインPC側）で試すかを決める … 要オーナー確認
- [ ] 初回取り込みの実測を残す（何通で何分・何MB か。README に数値で書く）
- [ ] `restore.py`（`.eml` を IMAP APPEND で戻す）… 削除を実運用する前に用意したい
- [ ] **Tailscale を入れる**（外出先からスマホで見るため。人の作業＝アカウントログインが要る）
- [ ] メインPCで常駐させるときに `/bin/bash` へフルディスクアクセスを付与（Dropbox読み取り）
- [ ] メインPCへ渡すか決める（常駐させるなら launchd 登録・ポート8535。サブPCでは常駐させない）

## 完了

- [x] DB設計（accounts/folders/messages/attachments/delete_log/FTS5 trigram）
- [x] 取り込み（`sync.py --sync`）… 原本 .eml＋添付＋SHA256、`synced_at` を記録
- [x] サーバー側削除（`--delete` / `--yes`）… 14日ルール＋5つの照合＋UID EXPUNGE
- [x] 閲覧UI（`app.py` / port 8535 / 127.0.0.1）
- [x] `smoke_test.py`（偽IMAPサーバーで30項目。本物には繋がない）
- [x] **置き場の分離**（原本＝個人Dropbox / DB＝ローカル）と `--rebuild`（DBを原本から再構築）
- [x] **パスワード認証＋`run-lan.sh`**（未設定ならLANに出さない）とスマホ表示の調整
- [x] `import_from_mail.py`（Mail.appから取り込む。パスワード不要・削除対象にならない）
- [x] **実データで確認**（Mail.app経由で19通・4.0MB・添付2件。`--verify` 問題0件、
      日本語検索・添付保存・画面まで確認。2026-08-20）

## 決めたこと（蒸し返さない）

- **画面からサーバーのメールは消せない。** 取り違えて押す事故を無くすため、削除はCLIだけ。
- **削除は既定で無効**（`.env` の `ARCHIVE_DELETE_ENABLED=0`）。有効にしても `--yes` が要る。
- **未読・フラグ付き・ゴミ箱は消さない**（オプションで解除はできる）。
