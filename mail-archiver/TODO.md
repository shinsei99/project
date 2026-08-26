# TODO — メールアーカイバ（mail-archiver）

## 進行中・次にやること

- [ ] **初回の自動削除の結果を見届ける**（今夜2時 or 手動 kickstart）。daikyocorp 44,648通・21.4GB が
      サーバーから消える見込み。翌朝 `local/sync-daily.log` と `--stats` の「サーバーに残存」で確認
- [x] **常駐化＋毎日2時の自動取り込み＋1年保存期間の自動削除**（2026-08-26）。launchd 2本登録
      （`com.shinsei.mail-archiver` 8535閲覧・`com.shinsei.mail-archiver-sync` 2時）。詳細は SESSION_LOG
- [x] **Desktop/社内ツール/メールアーカイバ.app を作成**（他アプリの様式に合わせたアイコン付き）
- [x] **受信/送信・期間・アカウントで絞り込めるUI**（2026-08-26。説明文削除・指標をサイドバーへ）

- [x] **shinsei-pm.co.jp（info@）の正規IMAP取り込みを確立**（2026-08-26）。当てずっぽうは解けず、
      アルファメール会員サイトに管理者 `administrator@shinsei-pm.co.jp`/`u22u9D2s` でログインし
      info@ のパスワードを `Seed9999sp!` に**再設定**→キーチェーン登録→`imap.shinsei-pm.co.jp:143` で
      LOGIN OK・`--sync` 成功（サーバー側INBOXは1通のみ。過去分254通は 8/25 Mail.app 経由で取得済み）。
      ★Mail.app 側の info@ にも新パスワードを入れ直すこと。詳細は SESSION_LOG 2026-08-26。
- [ ] **会社アカウントの本体同期が終わったら「Sent Messages」を追加取得**（この回は除外設定を
      読み込んだ後に外したので送信箱を飛ばしている。`python3 sync.py --sync --account daikyocorp.co.jp`
      を再実行すれば増分で送信箱だけ入る）
- [x] **shinichi-washimi.jp を正規IMAPで取り込み**（2026-08-26・パス `kyobashi99!`・キーチェーン登録済み）。
      iCloud / Google は**Mail.app経由のまま据え置き**（オーナー判断・App用/アプリパスワードは発行しない）

- [ ] **7アカウントのパスワードをキーチェーンに入れる**（人の作業・ターミナル.appから1行ずつ）。
      `security add-generic-password -s mail-archiver -a <メールアドレス> -w`
      … iCloud と Gmail は**App用パスワード**の発行が先（2ファクタのため）。
      入れ終わったら `python3 sync.py --list-accounts` で「パスワードあり」を確認
- [ ] **メールDBを git の履歴からも消すか決める**（2026-08-25 に追跡は外した。
      過去のコミット `82c07b64` には実メール19通ぶんが残っている。消すなら force push が要る）
- [ ] 取り込みの最初の1本を決める（`--account daikyocorp.co.jp --since-days 7 --limit 20` から）
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
