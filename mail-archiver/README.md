# メールアーカイバ（mail-archiver）

IMAPサーバーの容量を空けるための、**ローカル保管＋全文検索**アプリ。
メールを手元に完全な形（`.eml` 原本）で落としておき、**取り込みから14日以上たったものだけ**を
サーバー側から消す。消すのはコマンドからだけで、画面からは消せない。

- 分類: ツール（メール本文＝個人情報を含むので**社内LANには出さない**）
- 閲覧UI: Streamlit / port **8535** / **127.0.0.1 固定**
- 依存: 標準ライブラリ（`imaplib` / `email` / `sqlite3`）＋ Streamlit だけ

## なぜ作ったか

`shin@daikyocorp.co.jp` の IMAP メールボックスが約40GB まで肥大化し、ドメイン総容量の107%に達して
**受信も送信も止まった**（2026-08-08）。そのときは管理画面から Dovecot の索引を消し、
大きいフォルダを削って98%まで下げて復旧させたが、**溜まり続ける構造は変わっていない**。
「サーバーには最近の分だけ置き、古い分は手元で検索する」形にするのがこのアプリ。

## 構成

| ファイル | 役割 |
|---|---|
| `db.py` | SQLite のスキーマと検索。FTS5(trigram) で日本語の部分一致検索 |
| `imap_util.py` | IMAP 接続・フォルダ名(修正UTF-7)のデコード・メールの分解 |
| `sync.py` | **CLI**。取り込み(`--sync`)・サーバー側削除(`--delete`)・点検(`--verify`) |
| `app.py` | **閲覧UI**（Streamlit）。検索・本文表示・添付/原本のダウンロード |
| `import_from_mail.py` | **Mail.app から取り込む**（IMAPパスワード不要）。取り込んだ分は削除対象にならない |
| `smoke_test.py` | 偽IMAPサーバーでの通し検証（本物には繋がない） |
| `run-lan.sh` | **メインPC専用**。0.0.0.0＋パスワードでスマホから開けるようにする |
| `config.py` | 設定の読み込み（キーチェーン対応）。**アカウント1つにつき設定ファイル1本** |
| `import_mail_accounts.py` | **Mail.app のアカウント設定を丸ごと取り込む**（AppleScript。パスワードは取らない） |

```
IMAP サーバー ──(BODY.PEEK[] で取得。既読フラグを変えない)──▶ data/raw/**.eml  ← 原本
                                                          └▶ data/mail.db     ← 索引・検索
                                                          └▶ data/attachments/ ← 添付
        ▲                                                        │
        └──(14日経過＋5つの照合をすべて通ったものだけ \Deleted + UID EXPUNGE)──┘
```

## 置き場（2026-08-20 決定）

| もの | 置き場 | なぜ |
|---|---|---|
| 原本 `.eml` ・添付・サイドカー `.eml.json` | **個人Dropbox**（`ARCHIVE_STORE_DIR`） | 書いたら二度と書き換えない（write-once）ので同期と喧嘩しない。2台から見えてバックアップにもなる |
| SQLite の索引 `mail.db` | **ローカル固定**（`ARCHIVE_DB_PATH`＝`mail-archiver/local/`） | **同期フォルダに置くと壊れる。** 本体・WAL・shm を同時に書くので、書き込み途中でDropboxが持っていくと不整合になる |

**索引DBは git にも入れない**（2026-08-25）。件名・本文・差出人がそのまま入っており、
`data/` と同じくメール本文の塊だから。**2026-08-20 の `82c07b64` で実メール19通ぶんが
public リポジトリに入っていた**（`.gitignore` で `data/` と `.env` は外したが `local/` を
書き忘れていた）。追跡は外したが、**過去のコミットには残っている**。

**2台のPC・スマホからどう読むか**: 配るのは**Dropboxの原本だけ**で、索引は各PCが自分で作る。

```bash
python3 sync.py --rebuild     # Dropboxの .eml＋サイドカーから索引を作り直す
```

実測（2026-08-25 メインPC）: **19通・添付2件・失敗0**。スマホからは、メインPCで `run-lan.sh` を
起動して社内WiFi（またはTailscale）で開く。**DBそのものは同期させない**（壊れるため）。

**会社の共有Dropboxには置かない。** メール本文と添付が同期先の全員に見える。個人Dropbox側に置く。

DBが壊れても、原本さえあれば作り直せる:

```bash
python3 sync.py --rebuild     # 原本(.eml)＋サイドカーからDBを再構築
```

サイドカー（`<uid>.eml.json`）に `synced_at`・UID・UIDVALIDITY・フラグ・添付一覧・SHA256 を
書いてあるので、**作り直しても14日ルールの起点がずれない**。サーバーから消したメールには
`<uid>.eml.deleted.json` の墓標が残るので、その状態も復元できる。
（実測: DBを削除 → `--rebuild` で19通・添付2件を復元、`--verify` 問題0件・検索も復旧）

## データベース設計

| テーブル | 中身 |
|---|---|
| `accounts` | 接続先（ホスト・ユーザー）。パスワードは**入れない** |
| `folders` | フォルダ。`raw_name`(修正UTF-7) と表示名、**`uidvalidity`**、`last_seen_uid` |
| `messages` | 1通1行。件名/From/To/日付/サイズ/フラグ/本文平文、`raw_path`＋`raw_sha256`、**`synced_at`**、`server_state`(present/deleted/gone) |
| `attachments` | 添付1件1行。ファイル名・MIME型・保存パス・SHA256 |
| `delete_log` | 削除の台帳。dry-run／deleted／skipped と**その理由**を全部残す |
| `messages_fts` | FTS5(trigram) の索引（件名・宛先・本文） |

- **`synced_at` が2週間ルールの起点**。「メールの日付」ではなく「手元に取り込んだ日時」で数える。
- **原本は `.eml` ファイル、DBは索引**という役割分担。DBが壊れても原本からやり直せる。

## 複数アカウント（2026-08-25 メインPCで対応）

メインPCの Mail.app には **7アカウント**入っている（iCloud / 会社 / 独自ドメイン4本 / Gmail）。
**設定はアカウント1つにつき1ファイル**（`.env.mail-archiver.<slug>`）にしてある。
1本に詰め込まないのは、**消す操作がどのアカウントに対するものかをコマンドに残す**ため。

```bash
python3 import_mail_accounts.py --list    # Mail.app に何があるか見るだけ
python3 import_mail_accounts.py           # 設定ファイルを作る（既にある物は上書きしない）
python3 sync.py --list-accounts           # 設定済み一覧とパスワードの有無
python3 sync.py --sync --all-accounts     # 全アカウントを順に取り込む
python3 sync.py --sync --account daikyocorp.co.jp --since-days 7 --limit 20   # 1本だけ
```

- **`--all-accounts` と `--delete` は併用できない。** 削除は必ず `--account <slug>` で名指しする
- 設定ファイルは**gitに入らない**（`.env.mail-archiver.*` は除外・`.example` だけ追跡）。
  **もう1台のPCでは、そのPCで `import_mail_accounts.py` を実行する**（アカウント構成が違うため）

### パスワードは取り込めない（調べた結果）

Mail.app のIMAPパスワードは**ログインキーチェーンには無い**。`security dump-keychain` で見える
inet項目は ftp が2件だけで、メール系は0件だった（データ保護キーチェーン側にあるため
他プロセスからは読めない）。**アカウントごとに人が1回だけ登録する**:

```bash
security add-generic-password -s mail-archiver -a <メールアドレス> -w
```

- **ターミナル.app から叩く。** Claude Code の `!` から叩くと入力待ちが効かず**空パスワードで登録される**
- **iCloud と Gmail は App用パスワード**が要る（2ファクタのため。通常のログインパスワードでは通らない）

### ポート143は STARTTLS（つまずいた点）

Apple Mail の「ポート143＋SSLを使う」は **STARTTLS**（平文で繋いでから暗号化に切り替える）のこと。
7アカウント中**5本が143番**で、`IMAP4_SSL` で繋ぐと必ず失敗する。`IMAP_SECURITY`（`ssl` /
`starttls` / `none`）で指定でき、空なら **993→SSL・143→STARTTLS** と自動で決める。

## 使い方

```bash
cp .env.mail-archiver.example .env.mail-archiver   # 接続情報を書く（gitには入らない）
python3 sync.py --sync                # 取り込み（初回は時間がかかる。--since-days 30 で試せる）
python3 sync.py --stats               # 何通・何MB 溜まったか
./run.sh                              # 閲覧UI → http://127.0.0.1:8535
python3 sync.py --verify              # 保存済み .eml が壊れていないか総点検
python3 sync.py --delete              # 削除候補を出すだけ（dry-run。何も消えない）
python3 sync.py --delete --yes        # ★実際にサーバーから消す
python3 smoke_test.py                 # 偽サーバーでの通し検証（本物に繋がない）

# IMAPのパスワードがまだ無いとき（macOS標準メールから直接もらう）
python3 import_from_mail.py --list                            # アカウントとメールボックス
python3 import_from_mail.py --mailbox "Sent Messages" --limit 20
```

主なオプション: `--days 14`（据置日数）／`--folder <名前>`／`--max-delete 500`（1回の上限）／
`--include-unseen`（未読も対象に）／`--include-flagged`（フラグ付きも対象に）／
`--since-days N`（新しいものだけ取り込む）

## 夜間の作業の並び（2026-08-28 オーナー指定）

**Claude の定額枠を取り合わないよう、時間で分けている。** 2026-08-27 夜に翻訳が枠を使い切り、
01:00 の OCR を巻き添えにして21秒で止めた反省から。

| 時刻 | 処理 | 実測の所要 |
|---|---|---|
| 22:35 | note へ投稿（Claude不要・Playwright） | 数分 |
| 22:45 | 記事を1本書く（`ai-tools-base/daily-write`） | 未計測 |
| **00:30** | **メール取込＋英語メールの翻訳100通＋ベクトル** | 取込7分40秒＋翻訳約15分＝**1時間以内** |
| 01:00〜02:00 | （緩衝帯。翻訳が長引いても次とぶつからない） | |
| **02:00〜04:00** | スキャンPDFのOCR（300件 or 2時間） | 1件約2分＝最大60件 |

**翻訳の上限を上げるときは、この枠に収まるかを確かめてから。** `TRANSLATE_MAX` で変えられる。
一度に全部やろうとすると枠を使い切り、他のジョブを巻き添えにする（2026-08-27に実際に発生）。

## スマホから見る

`run.sh`（127.0.0.1）は自分のPCからしか開けない。スマホから見るには **メインPCで `run-lan.sh`**
を使う。パスワード（`.env.mail-archiver` の `UI_PASSWORD`）が未設定なら**起動を拒否**し、
仮に起動できても**アプリ側が画面を出さずに止める**（メール本文を扱うため、素通りにしない）。

```bash
# .env.mail-archiver に UI_PASSWORD=... を書いてから
./run-lan.sh          # 0.0.0.0:8535。社内WiFiのスマホから http://192.168.1.105:8535
```

画面はスマホの縦画面でも崩れないようにしてある（指標は2列に折り返し・タップ領域44px・
入力欄16px＝iOSの勝手な拡大を防ぐ）。実測で 390×844 / 768 / 1440 とも横スクロールなし。

### 外出先からも見たいとき（Tailscale）

**公開URLは作らない。** Tailscale は自分のApple ID/Googleアカウントで繋いだ端末どうしだけが
繋がる私設ネットワークなので、メールの中身を外に晒さずにスマホから開ける。

> **✅ 2026-08-28: 自動で起こすようにした。** `com.shinsei.tailscale-keepalive`（Mac起動時＋5分ごと）が
> 止まっていたら `open -a Tailscale` する。実体は `_launchd/tailscale-keepalive.sh`、
> ログは `~/Library/Logs/com.shinsei.tailscale-keepalive.log`（起こしたときだけ書く）。
> **Tailscale.app は自動起動の設定に一切入っていなかった**（launchd登録もログイン項目も無し）ため、
> 手で起こしたときしか動かず、2026-08-28 の午前中だけで2回落ちた。
>
> **⚠️ それでも開けないときは、まず Mac mini の Tailscale が動いているかを見る**（2026-08-27に実際に発生）。
>
> ```bash
> /Applications/Tailscale.app/Contents/MacOS/Tailscale status        # → "Tailscale is stopped." なら止まっている
> /Applications/Tailscale.app/Contents/MacOS/Tailscale serve status  # → 中継先が出るか
> ```
>
> 直し方は **Mac mini で Tailscale.app を起動する**だけ（`open -a Tailscale`）。
> iPhone側のランプが点いていても、**Mac mini 側が止まっていれば届かない**。
> 管理画面では Mac mini が `not connected` に見える。
>
> **★紛らわしい罠**: Tailscale が止まっていると `serve status` が **`No serve config`** と出る。
> **設定が消えたわけではない**（起動すると `https://usermac-mini.tailfcc81a.ts.net (tailnet only)` と戻る）。
> ここで慌てて `tailscale serve` を叩き直す必要は無い。
>
> なお `serve`（Tailnet内だけ）と `funnel`（インターネット全体に公開）は別物。
> **メールには絶対に `funnel` を使わない。**

1. メインPCに Tailscale を入れてログイン（`brew install --cask tailscale` またはApp Store版）
2. iPhoneにも Tailscale を入れて**同じアカウント**でログイン
3. メインPCで `./run-lan.sh` を起動しておく
4. iPhoneのブラウザで `http://<メインPCのTailscale名>:8535`（例 `http://mac-mini:8535`）

※ **この作業は人がやる**（アカウントのログインが要るため）。2026-08-20時点で未導入。
※ ngrok のような公開URL方式は、URLを知られたら誰でも開けるのでこの用途では使わない。

## 削除の安全設計（ここがこのアプリの本体）

**鍵は3つ。全部開けないと消えない。**

1. `.env.mail-archiver` の `ARCHIVE_DELETE_ENABLED=1`
2. 実行時の `--delete`
3. 実行時の `--yes`（付けなければ**必ず dry-run**）

そのうえで **1通ごとに**次を全部確かめ、1つでも欠けたらその通は飛ばして理由を `delete_log` に残す。

| # | 確認 | 何を防ぐか |
|---|---|---|
| a | `synced_at` から14日以上 | 取り込んだ直後に消して、取り込み自体が失敗していた事故 |
| b | 原本 `.eml` が実在・**SHA256一致**・サイズ一致 | DBに行はあるが中身が0バイト／壊れている状態で消すこと |
| c | 添付ファイルがすべて実在 | 本文だけ残って添付が消えること |
| d | **UIDVALIDITY がサーバーと一致** | フォルダ再作成でUIDの意味が変わり、**別のメールを消す**こと |
| e | **Message-ID がサーバーと一致**（無ければサイズ一致） | UIDのずれで隣のメールを消すこと |
| f | 既読・フラグ無し | 未読／重要マークを勝手に消すこと |
| g | 除外フォルダでない（ゴミ箱・迷惑メール） | ゴミ箱を触ること |

さらに **`UID EXPUNGE`（UIDPLUS拡張）で「いま指定したUIDだけ」を消す**。
素の `EXPUNGE` は**そのフォルダで `\Deleted` が付いている他のメールも道連れにする**ため、
UIDPLUS が無いサーバーでは `--allow-full-expunge` を明示しない限り中止する。

**消してもローカルの原本は消えない。** `server_state` が `deleted` になるだけで、
`.eml` も添付もそのまま。UIから `.eml` をダウンロードすれば Apple Mail で開ける。

## Mail.app からの取り込み（パスワード不要の入口）

iCloud のように2ファクタ認証のアカウントは、外部アプリからのIMAPログインに **App用パスワード**
（appleid.apple.com で発行）が要る。Mail.app が使っている ATOKEN/OAuth のトークンは流用できない。
発行前でも中身を確かめられるよう、**Mail.app から AppleScript でメールのソースごと受け取る**
入口を用意した（`import_from_mail.py`）。

**ここから入れたメールは、サーバー側削除の対象に絶対にならない。** `server_state='local'`
（IMAP管理外）で保存しており、削除候補の抽出は `server_state='present'` だけを見るため。
UIDもIMAPのものではないので、取り違えて別のメールを消す余地が最初から無い。

限界: Mail.app が返す `source` はテキストなので、8bitのまま送られた本文は化ける可能性がある
（base64/quoted-printable の普通のメールは問題ない）。**原本の完全性が要るなら IMAP 経由**。
速度は **1通あたり約3秒**（`osascript` を1通ごとに起動するため。実測: 20通で58秒）。
IMAP経由のほうがずっと速いので、これはあくまで「パスワードが無いとき」の入口。

## 調べて分かった事実（次の担当が同じ調査をしないために）

- **`RFC822` で取ると `\Seen` が付く。** 取り込んだだけで未読が既読になる。`BODY.PEEK[]` を使う。
- **UID は UIDVALIDITY とセットでしか意味を持たない。** フォルダを作り直されると同じUIDが
  別のメールを指す。`messages` の一意キーに `uidvalidity` を含め、削除前に毎回突き合わせる。
- **フォルダ名は「IMAP修正UTF-7」**（`INBOX.&U9ZfFVFI-` ＝ `INBOX.取引先`）。UTF-16BE→base64で
  `/`→`,` に置換する独自形式。Python標準にデコーダが無いので `imap_util.py` に自前で持っている。
- **サーバー上のフォルダ名は NFD のことがある**（`ポータル` が `ホ`+`゚`）。表示名は NFC に正規化する。
  しないと同じ名前のフォルダが2つあるように見える。
- **FTS5 の `unicode61` では日本語が検索できない**（空白で区切られないため）。`trigram` を使うと
  3文字以上の部分一致が効く（SQLite 3.34+、macOS標準の3.43で動作確認）。2文字以下は LIKE に落とす。
- **iCloud は認証前に UIDPLUS を名乗らない。** 接続直後の `capabilities` だけを見て「非対応」と
  判断すると、使えるはずの `UID EXPUNGE` を諦めてしまう。**ログイン後に CAPABILITY を取り直す**。
- **Streamlit は再実行のたびに別スレッドで動くことがある。** SQLite接続を使い回すと
  `SQLite objects created in a thread can only be used in that same thread` で落ちる
  （2026-08-20に実データで発生）。`check_same_thread=False` で接続する。
- **件名が空のメールは普通にある。** 実データ19通が全部そうだった（iPhoneから自分宛に送るメモ）。
  一覧に「(件名なし)」が並ぶと使えないので、本文の冒頭を代わりに出している。
- **launchd の常時起動プロセスは Dropbox（CloudStorage）を読めない。** 書類キャビネット(8528)で
  踏んだのと同じTCCの問題で、`/bin/bash` にフルディスクアクセスを与えると通る。
  メインPCで常駐させるときは必ず引っかかるので先に手当てする。
- **削除だけでは容量は減らない。** `\Deleted` を立ててから `EXPUNGE` して初めて空く。
  （2026-08-08 の障害でも「ゴミ箱に入れただけ」では減らなかった）

## 未実装・これから

- `restore.py`（`.eml` を `IMAP APPEND` でサーバーへ戻す）は未着手。いまは手元の `.eml` を
  Apple Mail にドラッグして開く運用で足りる想定。
- **IMAP経由の取り込みは、まだ一度も本物のサーバーで実行していない**（2026-08-20時点）。
  iCloud の App用パスワードが未発行のため。検証は `smoke_test.py` の偽サーバーと、
  Mail.app 経由で取り込んだ実メール19通（4.0MB・添付2件）で行った。
  パスワードが用意できたら `--since-days 7 --limit 20` から試す。
