# KeyLine — NFC鍵・備品貸出管理

鍵や重要備品を「**NFCタグにかざすだけで、誰が・何を・いつ持ち出し、いつ返したか**」記録する社内ツール。
未返却・所在不明・誰が持っているか分からない、を防ぐ。

| | |
|---|---|
| 分類 | 不動産 |
| 本体 | **メインPC（Mac mini 192.168.1.105）** |
| port | **8534**（`0.0.0.0` バインド・社内LAN共有あり） |
| 構成 | FastAPI + SQLite（Python `/usr/bin/python3`） |
| 端末 | 鍵ボックス横の**鍵管理用スマホ1台**（iPhone・Safari）／管理者のPC |

---

## いちばん大事な単位

**NFCタグ1枚 = 1つの貸出管理単位（Asset）**

```
管理対象「本社正面入口」  ← NFCタグ1枚・貸出も返却もこの単位
  ├─ 鍵 12345
  ├─ 鍵 12346
  └─ 鍵 12347
```

鍵1本でも3本セットでも工具セットでも、**実際に貸し借りする単位**を1つの Asset にする。
鍵番号は鍵本体に刻印された番号で、**システムが採番するものではない**し、**NFC識別子とも別物**。

```
NFCタグ → nfc_identifier → assets → asset_items（鍵番号）
```

タグを交換しても `assets.id` は変わらないので、履歴も構成品も維持される。

---

## 全体の作り

```
メインPC 192.168.1.105:8534   ← アプリもDBもここに1本だけ
        │
        ├── /            管理画面   → 管理者のPCのブラウザ
        └── /t/<token>   貸出画面   → 鍵管理スマホのSafari（NFCで飛んでくる先）
```

**鍵管理スマホには何もインストールしない。** Safari で開くだけ。
だから App Store 審査もバージョンずれも無く、メインPCを直せばスマホ側も即座に最新になる。

---

## ★ 調べて分かったこと（再調査不要）

### 1. Safari は Web NFC に非対応。ブラウザから NFC は絶対に触れない

iOS / iPadOS / macOS のいずれの Safari も `NDEFReader` が `undefined`。有効化するフラグも無い。
Apple はネイティブ向けの Core NFC は出しているが、WebKit に Web NFC を入れていない
（2026年4月時点の世界シェア約6%、Chromium系 Android ブラウザのみ）。

→ **社内LANの Streamlit を Safari で開く方式では NFC が使えない。** これが方式決定の分岐点だった。

### 2. 代わりに使うのが「iOS バックグラウンドタグ読み取り」

NFCタグに **NDEF の URL レコード**を書いておくと、iPhone をかざすだけで通知バナーが出て、
タップすると Safari がその URL を開く。**アプリのインストールが要らない。**

- **iPhone XS 以降**のみ（iPhone X 以前は非対応）
- NDEF 書き込み可能なタグが必要（NTAG213/215/216 等）
- 通知は必ずユーザーがタップして承認する（勝手には開かない）
- 画面が点いている時のみ読む
- ご指示5に「NFC UID **またはタグに書き込んだID**」とあるので、**仕様の範囲内**

### 3. 🔴 未確認：平文 `http://` の LAN内IP でも通知が出るか

事例の多くは `https://` の公開URL。**タグが届いたら最初にこれを検証すること。**
黒だった場合の代替（調査済み・行き止まりではない）:

1. `keyline.daikyocorp.co.jp` の A レコードを **192.168.1.105 に向け**、DNS-01 チャレンジで
   Let's Encrypt 証明書を取得 → LAN内でも正規の HTTPS になる（ドメインは自社保有）
2. 自己署名証明書 + 各 iPhone に構成プロファイル（端末ごとに1回の手作業）

### 4. iPad は NFC を読めない

NFCリーダー自体が非搭載。NFC読み取りは **iPhone 7以降**、バックグラウンド読み取りは
**iPhone XS以降**。共用端末を置くなら **iPhone** でなければならない。

### 5. 将来ネイティブアプリにするなら（今は不要）

タグの実UIDを読む方式に替える場合、npm の実物をソースまで読んで確認した結果：

| パッケージ | 可否 |
|---|---|
| `@capgo/capacitor-nfc` 8.2.3（MPL-2.0） | ✅ `sessionType:'tag'` で `NFCTagReaderSession`。`NFCMiFareTag.identifier` 等からUID取得 |
| `react-native-nfc-manager` 3.17.2 | ✅ `NFCTagReaderSession` + `mifareTag.identifier`。Expo config plugin 同梱 |
| `@capacitor-community/nfc` | ❌ **npm に存在しない（404）** |
| `@capawesome-team/capacitor-nfc` | ❌ **npm 404**（有償スポンサー限定レジストリ） |
| `expo-nfc` | ❌ **v0.0.0 のプレースホルダ**。Expo に一次対応のNFCモジュールは無い |

いずれも iOS では `com.apple.developer.nfc.readersession.formats = ["TAG"]` エンタイトルメントが必須で、
Apple Developer Portal で App ID に「NFC Tag Reading」を有効化する手作業が要る。
`nfc_source` 列を用意してあるので、その時もスキーマ変更は不要。

### 6. `sqlite3.executescript()` は実行前に暗黙のCOMMITを発行する

**症状** マイグレーションが `cannot commit - no transaction is active` で落ちる。
**原因** `con.execute("BEGIN")` で外から囲んでも、`executescript()` がその場でトランザクションを閉じる。
**直し方** `BEGIN` / `COMMIT` を**スクリプト文字列の中に書いて** `executescript` に渡す。
SQLite は DDL もトランザクションに入るので、失敗すれば全部戻る（`db.py: migrate()`）。

### 7. 時刻だけでは履歴の全順序を保証できない

**症状** 同一秒に貸出が2件あると `ORDER BY checkout_at` の順序が決まらず、最新1件を取り違える。
**原因** タイムスタンプの精度の問題。ミリ秒に上げても、インメモリDBでは**同一ミリ秒に2件入る**ため解決しない。
**直し方** `ORDER BY checkout_at DESC, rowid DESC`。rowid は挿入順に増える SQLite の暗黙列。
Postgres へ移すときは rowid が無いので `seq bigserial` を足して置き換える。

※ミリ秒精度自体は監査記録として有用なので残してある。ただし
**秒精度とミリ秒精度を混ぜてはいけない**（`'...05.123Z' < '...05Z'` となり文字列比較が壊れる）。

### 8. SQLite の外部キーは接続ごとに既定でOFF

`PRAGMA foreign_keys = ON` を忘れた接続からは制約が丸ごと効かない。
**`db.connect()` 以外でSQLiteを開かないこと。**

---

## セキュリティ・個人情報

- 社内WiFi内のみ・`0.0.0.0` バインド。**インターネットには出さない**
- `data/` は **gitignore**（このリポジトリは public）。中身は貸出先の氏名・会社名・電話、
  身分証画像、鍵番号、物件名 — すべて個人情報・機密
- **身分証・名刺の画像は返却から30日で自動削除**する（`id_image_purged_at` に記録が残るので
  「撮ったが今は無い」と「そもそも撮っていない」を区別できる）
- OCR は `claude` CLI のビジョン（`/opt/homebrew/bin/claude`・APIキー不要）。
  既存の `baikai-generator/services/registry_parser.py` と同じ経路。
  **読み取りの瞬間だけ画像は Anthropic のサーバーへ送られる**
- NFC の値（URLのトークン）は**秘密ではない**。クローンされ得る前提で、
  トークンは検索キーとしてのみ使い、権限判定は必ずログインセッション側で行う

---

### 9. 🔴 タグに書くURLは「アクセス中のURL」から作ってはいけない

管理者が `http://localhost:8534` で開いていると、詳細画面に localhost 入りのURLが出る。
それをタグに書くと**スマホからは自分自身を指すので永久に開けない**。しかもタグは
物理的に書き直しになるため、気づくのが遅いほど痛い。

→ `services.lan_base_url()` が常に **LANのIP** を返す。`KEYLINE_BASE_URL` で上書き可。
   さらに `run.sh` が **en1（192.168.1.105）** を明示する。このMacは
   en0=192.168.1.140 / en1=192.168.1.105 の2枚刺しで、CLAUDE.md の
   「配布は .105 で統一」に従うため（自動検出だと en0 の .140 が返ってしまう）。

---

## 使い方

### 初回だけ（管理者・PC）

```bash
cd ~/keyline
/usr/bin/python3 -m pip install --user fastapi 'uvicorn[standard]' python-multipart
/usr/bin/python3 seed.py          # 組織・管理者・鍵管理端末アカウントを作る
./run.sh                          # 手動起動（常駐にするなら _launchd/install.sh）
```

1. `http://192.168.1.105:8534` を開いてログイン
2. **ボックス**を登録（BOX-01 / 本社1F鍵ボックス）
3. **管理対象**を登録（名前・鍵番号を複数・ボックス・位置）
   → 「NFCタグ用のURLも同時に発行する」にチェックしておく
4. 詳細画面に出る **`http://192.168.1.105:8534/t/xxxx`** を、
   NFCタグに **NDEFのURLレコード**として書き込む（iPhoneの無料アプリ「NFC Tools」等）

### 鍵管理用スマホ（1台・1回だけ）

1. **社内WiFi**に繋ぐ（LTEだと 192.168.1.105 に届かない）
2. Safari で `http://192.168.1.105:8534` を開き、**operator アカウント**でログイン
3. 共有ボタン →「ホーム画面に追加」でアイコンから開けるようにする（任意）

以後ログインは不要（Cookieの有効期限は365日）。

### 毎日の運用

```
持ち出す：かざす → 相手を選ぶ → ［貸出する］
戻す　　：かざす → ［返却する］
```

常連の業者は一覧から**タップ1回**。初見の相手だけ「＋ はじめての相手に貸す」で
名前を入れるか、**免許証・名刺を撮影**すれば自動で入る。

### 常駐にする（メインPCのみ）

```bash
~/keyline/_launchd/install.sh
```

`com.shinsei.keyline`（本体・8534）と `com.shinsei.keyline-purge`（画像の自動削除・毎日3:30）
を登録する。**サブPCでは実行しないこと**（CLAUDE.md の役割分担）。

---

## 開発

```bash
cd ~/keyline
/usr/bin/python3 db.py                  # DB作成・マイグレーション適用
/usr/bin/python3 tests/test_schema.py   # スキーマの制約テスト（61件）
/usr/bin/python3 tests/test_flow.py     # 画面を通しで叩くテスト（35件）
/usr/bin/python3 purge.py --dry-run     # 削除対象の画像を確認（消さない）
```

`test_flow.py` はテスト専用の一時DBとサーバーを自分で立てるので、**本番DBには触らない**。

Python は **`/usr/bin/python3` 固定**（他アプリと同じ。venv Python だと `claude`
サブプロセスが SIGSEGV する既知の問題がある）。依存は `pip install --user` で入れる。

### ファイル

| | |
|---|---|
| `app.py` | FastAPI のルーティング。画面はここ |
| `services.py` | 業務ロジック。**貸出・返却の要はここ**（3層で二重貸出を防ぐ） |
| `auth.py` | パスワード（PBKDF2）とセッション |
| `ocr.py` | 免許証・名刺の読み取りと、画像の保存・削除 |
| `db.py` | 接続とマイグレーション。**SQLiteを開く経路はここだけ** |
| `purge.py` | 画像の自動削除（launchdで毎日実行） |
| `seed.py` | 初期セットアップ（`--demo` でサンプル投入） |

### まだやっていないこと

- **タグ到着後の実機検証**（上の「3.」が最優先）
- 利用者（users）の追加・パスワード変更の画面（いまは `seed.py` と CLI のみ）
- 返却期限が近い／過ぎた鍵の通知（Chatwork/LINE）。ご指示30で将来拡張とされているもの
