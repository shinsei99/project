# 社内メールアーカイバ（company-mail-archiver）

**大京商事の社員のメールを手元に保管し、AI業務マネージャー（大京商事）の知識として使えるようにする。**

- 分類: 不動産（社内業務）／ port **8538** ／ **127.0.0.1 固定**（社内LANにも出さない）
- 個人用の「メールアーカイバ」（8535）とは**別のDB・別の保管先**。中身は一切混ざらない
- **サーバーからは1通も消さない**（個人用にある削除機能は、このアプリでは使わせない）

## ★コードを複製していない（ここが設計の要）

画面も取り込みも**`mail-archiver/` のコードをそのまま動かしている**。違うのは
「どの設定を読み、どのDBに書き、何という名前で表示するか」だけで、それは環境変数で渡す。

```bash
MAIL_ARCHIVER_ENV=…/.env.company-mail-archiver          # 共通設定
MAIL_ARCHIVER_ENV_DIR=…/company-mail-archiver           # 社員ごとの設定の置き場
MAIL_ARCHIVER_ENV_PREFIX=.env.company-mail-archiver.    # その名前の頭
MAIL_ARCHIVER_DB=…/local/company-mail.db                # 索引（**ローカル固定**）
MAIL_ARCHIVER_DATA_DIR=…/company-mail-archive           # 原本と添付
```

**なぜ複製しないか**: 複製すると必ず分岐して、片方だけ直した状態になる。
この作業ツリーでは実際にそれで事故が起きている（同じ型のコードが2つあり、
直したはずの不具合が別の場所に残る）。**直すのは常に `mail-archiver/` の1本。**

## ★守ること（機械で止めている）

`guards.py` が動く前に点検し、1つでも引っかかったら**何もせずに止まる**。

| 守ること | 止め方 |
|---|---|
| **社員のメールをサーバーから消さない** | 設定に `ARCHIVE_DELETE_ENABLED=1` があれば夜間ジョブを中止 |
| **会社の共有フォルダに置かない** | 原本・書き出し先が共有Dropbox配下なら中止（社員全員に見えてしまうため） |
| **会社の壁**（大京商事と新誠を混ぜない） | 知識索引へ渡すとき `company='大京商事株式会社'` を必ず指定 |
| **社内LANにも出さない** | `run.sh` は `127.0.0.1` 固定。`run-lan.sh` は用意しない |

## 使い方

```bash
./run.sh                                   # 画面 http://127.0.0.1:8538
/usr/bin/python3 guards.py                 # 安全弁の点検だけ
/usr/bin/python3 smoke_test.py             # 通し検証（サーバーには繋がない）
/usr/bin/python3 export_to_knowledge.py --dry     # 何を知識に入れる/外すかを見るだけ
./sync-daily.sh                            # 取り込み→添付の中身→知識索引（夜間ジョブと同じ）
```

取り込みそのものは `mail-archiver` のCLIを、このフォルダの設定で呼ぶ:

```bash
export MAIL_ARCHIVER_ENV="$PWD/.env.company-mail-archiver" \
       MAIL_ARCHIVER_ENV_DIR="$PWD" \
       MAIL_ARCHIVER_ENV_PREFIX=".env.company-mail-archiver." \
       MAIL_ARCHIVER_DB="$PWD/local/company-mail.db"
../mail-archiver/.venv/bin/python3 ../mail-archiver/sync.py --list-accounts
../mail-archiver/.venv/bin/python3 ../mail-archiver/sync.py --sync --account tanaka --since-days 30 --limit 20
```

## 社員1人を追加する手順

1. `.env.company-mail-archiver.example` を写して `.env.company-mail-archiver.<slug>` を作る
2. パスワードを**ターミナル.appから**キーチェーンに入れる（Claude Code の `!` からは空で登録される）
   ```bash
   security add-generic-password -s company-mail-archiver -a tanaka@daikyocorp.co.jp -w
   ```
3. `sync.py --list-accounts` で「パスワードあり」を確認
4. **少量で試す**: `--sync --account <slug> --since-days 7 --limit 20`
5. 画面で中身を確認 → 問題なければ夜間ジョブに任せる

## 知識索引への渡し方（AI業務マネージャー）

`export_to_knowledge.py` が次をやる。

1. DBから**業務メールだけ**を選ぶ
2. 1通1ファイルの `.md` に書き出す（本文＋**添付から取り出した文字**）
3. `chatwork-ai-manager` の `knowledge.ingest_folder(company='大京商事株式会社')` で索引に入れる

**入れないもの**（入れるほど良いわけではない。メルマガが混ざるとAIの回答が薄まる）:

| 外すもの | 見分け方 |
|---|---|
| メルマガ・広告 | `List-Unsubscribe` ヘッダがある |
| 一斉配信 | `Precedence: bulk / list / junk` |
| 自動送信 | `Auto-Submitted: auto-*` |
| 通知メール | 差出人が `noreply` / `no-reply` / `mailer-daemon` / `postmaster` |
| 中身が無いもの | 本文も添付の中身も空 |

**外した理由は必ず数えて出す**（黙って捨てない）。`--dry` で内訳だけ見られる。

**★`info@` を機械的に外さない。** 取引先の窓口アドレスが `info@` であることは普通にあり、
外すと業務メールが丸ごと落ちる（回帰テストに入れてある）。

## 夜間の並び

| 時刻 | 何を |
|---|---|
| 00:30 | 個人のメールアーカイバ（8535） |
| 02:00〜 | 共有フォルダのスキャンPDFのOCR（AI業務マネージャー） |
| **03:30** | **社内メール**の取り込み → 添付の中身 → 知識索引へ |

重ならないように後ろへ置いてある（OCRはCPU、取り込みは回線を使う）。

## まだ決まっていないこと（人が決める）

- **対象の社員とアドレス**（誰の分を入れるか）
- **パスワードの入手方法**（管理者画面で再設定するか、本人に入力してもらうか）
- **社員への周知**（会社のメールを会社が保管し、社内AIの参照先にすること）
- 過去分をどこまで遡るか（既定は知識索引が直近365日。取り込み自体は全期間）
