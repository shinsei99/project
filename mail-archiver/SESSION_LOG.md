# SESSION_LOG — メールアーカイバ（mail-archiver）

## 2026-08-25（メインPC）

### 完了したこと

- **メインPCで初起動**（このPCには `.venv` が無かったので作成から）。`127.0.0.1:8535` で HTTP 200、
  画面も目視（保存19通・添付2件・サーバー残存0）。起動は直下の **`./app-start.sh mail-archiver`** に統一。
- **Mail.app のアカウント設定7件を取り込んだ**（`import_mail_accounts.py` を新設）。
  AppleScript で Mail.app に問い合わせ、`.env.mail-archiver.<slug>` を1アカウント1本で書き出す。
  DBの `accounts` 表にも登録するので、画面の絞り込みに出る。**パスワードは取らない**（後述）。
- **複数アカウント対応**: `sync.py --sync --all-accounts` / `--account <slug>` / `--list-accounts`。
  **`--all-accounts` と `--delete` は併用禁止**にした（消す操作はアカウントを名指しさせる）。
- **STARTTLS に対応**（`imap_util.connect` に `security` を追加）。7件中5件が **143番ポート**で、
  従来の実装は `IMAP4_SSL` で繋ぎにいくため**全部失敗する状態**だった。
- `config.load(env_file)` … ファイルを明示したときは**環境変数で上書きしない**。
  複数アカウントを回すとき、シェルに残った `IMAP_USER` が全アカウントに被さる事故を防ぐ。
- `smoke_test.py` に 11) を追加（接続方式の判定・環境変数の非干渉）。**全項目合格**。
- **Dropboxの原本から索引を作り直せることを実測**: `sync.py --rebuild` で **19通・添付2件・失敗0**。
  サブPCでも同じDropboxを見て `--rebuild` すれば同じ状態になる（DBは配らない）。

### 発生したエラーと解決策

- **★実メール19通のDB（`local/mail.db`）が public リポジトリに入っていた** → 原因は直下
  `.gitignore` の `!mail-archiver/**` で全許可した際、`data/` と `.env` は除外したが
  **`local/`（索引DB）の除外を書き忘れていた**（2026-08-20 `82c07b64`）。
  → `git rm --cached` で追跡をやめ、`.gitignore` に `mail-archiver/local/` を追加。
  **索引DBもメール本文の塊**（件名・本文・差出人が入る）。**過去のコミットには残っているので、
  履歴からの削除は別途判断**（force push が要る）。
- `.env.mail-archiver.<slug>` も同じく全許可に引っかかっていたので `mail-archiver/.env.mail-archiver.*`
  を除外に追加（`.example` だけ `!` で残す）。
- Mail.app のIMAPパスワードは**ログインキーチェーンには無い**（`security dump-keychain` の
  inet項目は ftp が2件だけ）。データ保護キーチェーン側にあるため、**他プロセスからは取れない**。
  → 各アカウント1回ずつ人が `security add-generic-password -s mail-archiver -a <addr> -w`。
  **ターミナル.app から叩くこと**（Claude Code の `!` からだと空パスワードで登録される）。

### 次回への引き継ぎ事項・未解決の課題

- **パスワード未登録＝IMAP取り込みはまだ0件**（7アカウントとも）。iCloud と Gmail は
  2ファクタのため **App用パスワード**の発行が要る（appleid.apple.com / myaccount.google.com）。
- **履歴からメールDBを消すか**（`git filter-repo` ＋ force push。もう1台は取り直しが必要）。
- サブPCでは `import_mail_accounts.py` をそのPCで実行する（設定ファイルは git で配らない）。

## 2026-08-20（サブPC）

### 完了したこと

- 新規アプリとして作成。IMAPサーバーの容量圧迫（2026-08-08 に受信も送信も止まった件）への恒久策。
- DB設計 … `accounts` / `folders` / `messages` / `attachments` / `delete_log` ＋ FTS5(trigram)。
  **`synced_at`（ローカル取り込み日時）を messages に持たせ、これを14日ルールの起点にした。**
- `sync.py --sync` … 原本 `.eml` をディスクに置いてから DB に入れる順序にした
  （DBに行があるのにファイルが無い状態を作らないため）。添付は別ファイル＋SHA256。
- `sync.py --delete` … 既定 dry-run。`--yes` で実行。1通ごとに **原本のSHA256・添付の実在・
  UIDVALIDITY・Message-ID・既読/フラグ・除外フォルダ** を照合し、通らなければ理由つきで飛ばす。
  削除は `\Deleted` ＋ **UID EXPUNGE**（UIDPLUS）。素の EXPUNGE は明示指定が無い限り実行しない。
- `app.py` … Streamlit の閲覧UI（port 8535 / **127.0.0.1**）。検索・本文・添付/原本ダウンロード。
  **画面からは消せない**（削除はCLIのみ）。
- `smoke_test.py` … 偽IMAPサーバーで30項目を通し検証。**本物のサーバーには一度も繋いでいない。**

### 発生したエラーと解決策

- 症状: フォルダ `.&MNswmjD8ML8w6w-` のデコード結果が「ポータル」と文字列比較で一致しない
  → 原因: サーバー側が **NFD**（`ホ` + `゚`）で持っている。デコード自体は正しかった
  → 直し方: 表示名を `unicodedata.normalize("NFC", ...)` で正規化。`raw_name` は触らない
  （サーバーへ送る名前は元のまま渡す必要があるため）。
- 踏む前に潰した所: `RFC822` で取得すると `\Seen` が付く（＝取り込んだだけで既読になる）ので
  `BODY.PEEK[]` にした。素の `EXPUNGE` は他人が付けた `\Deleted` まで消すので UID EXPUNGE にした。

### 追記（同日・実データで試した）

- このPCの Mail.app を調べたら **iCloud 1アカウントのみ**（`<自分のiCloudアドレス>` /
  p61-imap.mail.me.com:993 / SMTPも1つ）。`mail-merge-pro` は**自前で資格情報を持たず
  Mail.app のアカウントを読むだけ**の作りで、設定にも差出人情報は無かった（あるのは窓の位置だけ）。
- **iCloud は外部アプリからのIMAPに App用パスワードが要る**（AUTH=ATOKEN/XOAUTH2。Mail.app の
  トークンは流用できない）。未発行のため、**`import_from_mail.py` を追加**して
  Mail.app から AppleScript でソースごと取り込めるようにした。
  取り込んだ分は `server_state='local'` で入り、**削除候補（present）には一生入らない**。
- 実測: INBOX 1通 ＋ 送信済み18通 = **19通・4.0MB・添付2件**を取り込み、`--verify` で**問題0件**。
  日本語の全文検索（「デジタル書斎」→1件）と添付の保存（`領収書東條英利事務所.pdf` /
  RFC2231形式の日本語ファイル名）も画面で確認。取り込み速度は**1通あたり約3秒**（20通で58秒）。

### 発生したエラーと解決策（追記）

- 症状: 画面が `sqlite3.ProgrammingError: SQLite objects created in a thread can only be used
  in that same thread` で落ちた → 原因: Streamlit が再実行のたびに別スレッドで動くのに、
  `@st.cache_resource` で1本の接続を使い回していた → 直し方: `check_same_thread=False` で接続。
  書き込みは短いトランザクションだけで実質1人しか触らないため、SQLite自身のロックに任せる。
- 症状: iCloud が UIDPLUS 非対応に見え、削除が中止される → 原因: **認証前は名乗らない**だけだった
  → 直し方: ログイン後に `CAPABILITY` を取り直す（`imap_util.capabilities()`）。
- 気づき（バグではない）: 実データ19通は**すべて件名が空**だった（iPhoneから自分宛に送るメモ）。
  一覧が「(件名なし)」だらけになるので、件名が無いときは本文の冒頭を出すようにした。

### 追記2（同日・置き場の分離とスマホ対応）

- **原本は個人Dropbox・DBはローカル**に分けた（本人の判断）。
  `ARCHIVE_STORE_DIR` / `ARCHIVE_DB_PATH` を `.env` で指定する形。
  実際に `Library/CloudStorage/Dropbox-個人/mail-archive/` へ移し、DBは `mail-archiver/local/` に置いた。
- **DBを原本から作り直せるようにした**（`sync.py --rebuild`）。保存時に原本の隣へ
  write-once のサイドカー `<uid>.eml.json`（synced_at・UID・UIDVALIDITY・フラグ・添付・SHA256）を書く。
  **検証: DBを削除 → `--rebuild` で19通・添付2件を復元、`--verify` 問題0件、日本語検索も復旧。**
  サーバーから消したメールには `<uid>.eml.deleted.json` の墓標を残すので、その状態も戻る。
- **画面のパスワード認証**（`UI_PASSWORD`）と `run-lan.sh`（0.0.0.0）を追加。
  パスワード未設定でLANに出そうとしたら、**シェル側でもアプリ側でも止める**
  （「未設定なら素通り」にはしない。扱うのがメール本文のため）。
- **スマホ表示**を調整（指標の折り返し・タップ領域44px・入力欄16px・上余白）。
  実測で 390×844 / 768×1024 / 1440×900 とも横スクロールなし。題字がヘッダに隠れていたのを直した。

### 次回への引き継ぎ事項（更新）

- **Tailscale は未導入**（外出先から見るのに要る）。アカウントのログインが必要なので**人の作業**。
  手順は README「外出先からも見たいとき」。
- **メインPCで常駐させるときは、`/bin/bash` にフルディスクアクセスが要る**
  （launchd は CloudStorage=Dropbox を読めない。書類キャビネットと同じ）。
- **IMAP経由の取り込みは未実行のまま。** iCloud の App用パスワードを発行して
  `security add-generic-password -s mail-archiver -a <自分のiCloudアドレス> -w` で入れれば、
  `.env.mail-archiver` は既に用意済みなのですぐ試せる（削除は無効のまま）。
- 実行中に **maisoku-converter が 127.0.0.1:8505 で起動していた**（10:30起動）。
  `maisoku-converter/` に未コミットの変更と未追跡フォルダ（`crop_component/`）があり、
  同じ時間帯に e-Stat のコミットも入っているので、**別セッションが並行して作業中**と判断して
  一切触っていない。バインドは 127.0.0.1 で規則どおり。

### 次回への引き継ぎ事項・未解決の課題

- **本番アカウントへの接続は未実施**（オーナー確認が要る）。初回は `--since-days 7 --limit 20` から。
- `restore.py`（`.eml` を APPEND で戻す）は未実装。削除を実運用する前に用意したい。
- メインPCへ渡して常駐させるかは未定。サブPCでは常駐させない（役割分担のとおり）。
