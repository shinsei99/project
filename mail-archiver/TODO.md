# TODO — メールアーカイバ（mail-archiver）

## 進行中・次にやること

- [ ] **shinsei-pm.co.jp のパスワードを明日また試す**（2026-08-25 に seed99 / seed9999 / Seed9999 /
      Seed99sp! / FileZillaのFTPパス の5回とも `Invalid username or password`。**連続失敗でロックの
      懸念があるため今日は打ち止め**）。確実なのは大塚商会アルファメールの契約マイページ
      （online.alpha-web.jp / ID 392311・初期PW u22u9D2s※要変更済みかも）→ メールアカウントの再設定。
      いまは Mail.app 経由で Sent 37＋Deleted 219 を取り込み済み（受信箱は空だった）
- [ ] **会社アカウントの本体同期が終わったら「Sent Messages」を追加取得**（この回は除外設定を
      読み込んだ後に外したので送信箱を飛ばしている。`python3 sync.py --sync --account daikyocorp.co.jp`
      を再実行すれば増分で送信箱だけ入る）
- [ ] shinichi-washimi.jp（お名前.com管理画面で再設定）/ iCloud（App用パスワード）/
      Google（アプリパスワード）の正規パスワードを入れてIMAPで取り直す（いまは Mail.app 経由）

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
