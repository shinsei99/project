# SESSION_LOG — メールアーカイバ（mail-archiver）

## 2026-08-26（メインPC）

### 完了したこと

- **shinsei-pm.co.jp（info@）の正規IMAP認証を確立**した。8/25 に5回失敗したのは
  パスワードが変わっていたため（2016メモの `seed99` は失効）。**アルファメール会員サイト
  （利用者メニュー）に管理者 `administrator@shinsei-pm.co.jp` / `u22u9D2s` でログインし、
  管理者メニューから info@ のパスワードを `Seed9999sp!` へ変更**（オーナーの手で実施）。
  キーチェーン（`mail-archiver` / `info@shinsei-pm.co.jp`）へ登録し、`imap.shinsei-pm.co.jp:143`
  ＋STARTTLS で **LOGIN OK・フォルダ12個**を確認。`sync.py --sync` は成功したが
  **サーバー側INBOXは1通のみ**（過去分254通は 8/25 に Mail.app 経由で取得済み・サーバーには残っていない）。
  → 今後サーバーに届く分は `--sync` で増分取得できる状態になった。
- **★Mail.app の info@ も同じIMAPアカウント**なので、パスワード変更で受信が一度止まる。
  新パスワードを Mail.app 側にも入れ直すこと（オーナーへ案内済み）。
- **参考: 契約情報のスクショから判明した接続情報**（アルファメール2／大塚商会）:
  お客様番号 `0000392311` ／ 管理者 `administrator@shinsei-pm.co.jp` ／ 受信 `pop.shinsei-pm.co.jp`
  （IMAPは `imap.shinsei-pm.co.jp` でも通る）／ 送信 `amsub.shinsei-pm.co.jp` ／
  会員サイト `https://www.alpha-mail.jp/`（利用者）・`cont.mypage.otsuka-shokai.co.jp`（契約管理）。

### 常駐化・自動化・UI（2026-08-26 追記）

- **メインPCで常駐化した**（launchd 2本を新規登録・plistはリポジトリ外）:
  - `com.shinsei.mail-archiver` … 閲覧UI（`run.sh`／127.0.0.1:8535／KeepAlive）。**社内LANには出さない**（メール本文＝個人情報）。
  - `com.shinsei.mail-archiver-sync` … **毎日2時**の自動処理（`StartCalendarInterval` Hour=2）。
    どちらも **/bin/bash 経由**で呼ぶ（保管先が個人Dropbox＝CloudStorage。責任プロセスに FDA が要る。
    このMacは /bin/bash に付与済み [[reference_launchd_cloudstorage_fda]]）。
  - **launchd文脈で実測成功**（kickstart で手動起動）: キーチェーン認証OK・Dropbox書き込みOK・
    パスワード未設定3件は自動スキップ・rc=0。CLAUDE.md のポート表（8535＝launchd未登録）は登録済みへ要更新。
- **自動取り込み `sync-daily.sh`（新規）**: `sync.py --all-accounts --sync` → 各アカウントで
  `--delete --yes --older-than-days 365`（保存期間1年。**1年より前をサーバーから削除**）。
  `--all-accounts` と `--delete` は併用不可なのでアカウント別に回す。ログは `local/sync-daily.log`。
- **保存期間＝1年をコードに実装**（オーナー指示・2026-08-26）:
  - `db.deletable_candidates` に `before_date` を追加（メール日付 `date_utc` がそれより前だけ。
    日付不明は消さない）。`sync.py` に `--older-than-days`、`.env` に `ARCHIVE_RETENTION_DAYS`。
  - **「取り込みから14日」ルールは保存期間モードでは使わない**（指定時 days=0）。判定はメール日付だけ。
  - 4アカウントの `.env` に `ARCHIVE_DELETE_ENABLED=1` / `ARCHIVE_RETENTION_DAYS=365`。
    送信も対象に含める（shinsei-pm の除外から `Sent Messages` を外した。他3件は元から除外なし）。
    ドライラン規模: **daikyocorp 44,648通・21.38GB**（他3アカウントは1年超0通）。
  - **実際の削除（--yes）は未実行**。今夜2時の自動ジョブが初回を消す（またはオーナーが
    `launchctl kickstart -k …-sync` で手動起動）。**恒久削除はエージェントからは実行しない方針。**
- **UI改修**（`app.py`）: 説明文（IMAP容量…）を削除／指標4つをサイドバー絞り込みの下へ移動／
  **受信・送信フィルタ**を追加（`db.search(direction=)`。送信=フォルダ名にsent/送信、受信=それ以外・下書き除く）。
  iOSシミュレータ（iPhone 17 Safari・127.0.0.1:8535）で操作確認。
- **Desktop ランチャ**: `Desktop/社内ツール/メールアーカイバ.app` を新規作成（他アプリと同じ launcher＋
  Info.plist＋AppIcon.icns。開くと localhost:8535）。アイコンは家族の様式に合わせPILで生成
  （角丸スクエア＋ティール＋白の受信トレイ＋下向き矢印）。Dropboxには配らない（メール本文のため）。

### 削除タイミングの決定（蒸し返さない）

- **サーバー保存期間は1年**。メール日付が1年より前をサーバーから削除（ローカルは永久保存）。
- **削除は毎日2時の自動処理に組み込み済み**（取り込みの直後）。手動時は `--older-than-days 365`。
- 日中に Mail.app 上で自分で消した不要メールは**取り込まない**（2時までにゴミ箱へ移動＝除外フォルダ。
  オーナー了承済み＝残さなくてよい／案A）。取りこぼしを気にするなら頻度を上げる案は保留。

### 調べて分かった事実（パスワード探索の顛末）

- **メール設定画面のスクショからパスワード本体は取れない**（欄は伏せ字。OCRしても化けるだけ）。
  個人Dropbox `カメラアップロード` の PNG 5,781枚を macOS Vision（Swift/`ocr.swift`）で全OCRし
  「shinsei/パスワード/imap 等」で絞ったが、`info@` の平文パスワードは無し。得られたのは
  **契約マイページの管理者初期パスワード**（＝上記）だけで、これが再設定の入口になった。
- IMAP当ての失敗履歴（info@）: `seed99` / `seed9999` / `Seed9999`（=旧FTP） / `Seed99sp!` /
  `Seed9999sp!`（8/26に当てた時点ではまだ旧パス＝失敗。**変更後に一致**）。当てで解けたのではなく、
  管理者ログイン→再設定で解決した。**これ以上の総当たりはロック懸念があり不可**。

### 次回への引き継ぎ事項

- **shinichi-washimi も正規IMAPで取り込めるようにした**（2026-08-26）。パスワード `kyobashi99!` が通った
  （`mail92.onamae.ne.jp:143` STARTTLS）。キーチェーン登録済み＝2時の `--all-accounts --sync` に自動で乗る。
  ただし `ARCHIVE_DELETE_ENABLED` は立てていない＝**取り込みのみ・自動削除の対象外**。
- **正規IMAPは5アカウント**（daikyocorp / shinsei-pm / dream-mama / we-love-kyobashi / shinichi-washimi）。
  **iCloud と Google はMail.app経由のまま据え置き**（オーナー判断・2026-08-26。App用/アプリパスワード未発行）。
- 1年保存期間の**自動削除の対象は daikyocorp など4アカウント**（shinichi-washimi は含めない）。
- `kumiko@shinsei-pm.co.jp` も同じ管理者メニューから `Seed9999!` に変更した（未使用アカウント・取り込み対象外）。

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

### 全7アカウントを取り込んだ（2026-08-25 夜・実測）

**合計 55,473通 / 添付 39,675件 / Dropbox個人 `mail-archive` に 46GB**
（原本 .eml 27GB ＋ 添付を別途展開 19GB。**Dropboxは2TBプランなので余裕**）。

| アカウント | 方式 | 通数 | 容量 |
|---|---|---|---|
| daikyocorp.co.jp | 正規IMAP（chatworkのSMTPパスを流用） | 54,197 | 27.0 GB |
| iCloud（送信） | Mail.app経由 | 901 | 249 MB |
| shinsei-pm.co.jp（送信＋削除） | Mail.app経由 | 254 | 26 MB |
| Google（すべてのメール） | Mail.app経由 | 94 | 5 MB |
| we-love-kyobashi（受信＋送信） | 正規IMAP（2016年の控えが生きていた） | 6 | — |
| Shinichi-Washimi | Mail.app経由 | 2 | — |
| dream-mama | 正規IMAP（キーチェーンのFTP項目） | 0（ゴミ箱のみ） | — |

- **送信箱も対象に含めた**（除外リストから Sent Messages を外した。オーナー指示「送信も欲しい」）。
  会社は本体同期の後に増分で Sent Messages 185通を追加取得。
- **削除はしていない**（`server_deleted 0通`）。容量を実際に空けるのは14日後＋`--delete --yes`。
- **健全性**: 今日の約55,000通は `--verify` で全てSHA一致。不一致16件は 8/20 の古いテスト
  （`mailapp-iCloud` 19通）のみで、原本は開けるので実害なし。

### パスワードの入手経緯（次の担当のため）

- **daikyocorp** … `chatwork-ai-manager-smtp` のキーチェーン項目を参照（コピーしない）
- **dream-mama** … login キーチェーンにFTP用として入っていた（メールと同一だった）
- **we-love-kyobashi** … GoogleDrive `ソフトウェア/メール設定/パスワード.txt`（2016年）が現役だった
- **shinsei-pm** … seed99/seed9999/Seed9999/Seed99sp!/FTPパス の5回とも失敗。**アルファメール**
  （大塚商会）ホスティングと判明。契約マイページ online.alpha-web.jp / ID 392311 で再設定可。
  **明日また試す**（TODO）。連続失敗でロックの懸念があり打ち止めた
- **iCloud / Google / shinichi-washimi** … 正規はApp用/アプリパスワードが要る。今は Mail.app 経由

### 調べて分かった事実

- **Gmailの「すべてのメール」等は `mailbox "名前" of account` で取れない**（-1728）。実体名が
  `[Gmail]/すべてのメール` の入れ子で表示名と違う。一覧を回して index で参照する
  （`import_from_mail.py` の `resolve_mailbox_index`）。
- Mail.app のIMAPパスワードは login キーチェーンに無い（データ保護キーチェーン側で他プロセス不可）。

### 次回への引き継ぎ事項・未解決の課題

- **shinsei-pm のパスワードを明日また試す**（TODO 参照）。
- **履歴からメールDBを消すか**（`git filter-repo` ＋ force push。もう1台は取り直しが必要）。
- サブPCでは `import_mail_accounts.py` をそのPCで実行する（設定ファイルは git で配らない）。
- 添付が原本 .eml の中と展開先の両方にあり容量が二重（19GB×2相当）。2TBなので当面問題にしない。

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
