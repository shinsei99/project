# SESSION_LOG — メールアーカイバ（mail-archiver）

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

- このPCの Mail.app を調べたら **iCloud 1アカウントのみ**（`s.washimi@icloud.com` /
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

### 次回への引き継ぎ事項（更新）

- **IMAP経由の取り込みは未実行のまま。** iCloud の App用パスワードを発行して
  `security add-generic-password -s mail-archiver -a s.washimi@icloud.com -w` で入れれば、
  `.env.mail-archiver` は既に用意済みなのですぐ試せる（削除は無効のまま）。
- 実行中に **maisoku-converter が 127.0.0.1:8505 で起動していた**（10:30起動）。
  `maisoku-converter/` に未コミットの変更と未追跡フォルダ（`crop_component/`）があり、
  同じ時間帯に e-Stat のコミットも入っているので、**別セッションが並行して作業中**と判断して
  一切触っていない。バインドは 127.0.0.1 で規則どおり。

### 次回への引き継ぎ事項・未解決の課題

- **本番アカウントへの接続は未実施**（オーナー確認が要る）。初回は `--since-days 7 --limit 20` から。
- `restore.py`（`.eml` を APPEND で戻す）は未実装。削除を実運用する前に用意したい。
- メインPCへ渡して常駐させるかは未定。サブPCでは常駐させない（役割分担のとおり）。
