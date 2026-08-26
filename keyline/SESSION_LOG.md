## 2026-08-26（サブPC）— KeyTagNFC が Guideline 2.1（デモ動画の提出要求）で差し戻された

### 完了したこと

- 審査メールの内容を記録した。**リジェクト（Rejected）ではなく Information Needed**＝
  情報が足りないので出せ、という状態。**バイナリは受理されたままなので build を上げ直す必要はない**
  （動画リンクを入れて ASC で返信すれば、そのまま審査が再開する）。

  | 項目 | 値 |
  |---|---|
  | Submission ID | `a47e6a37-ee0d-48dc-8a35-2559cb1b976b` |
  | 提出 | 2026-08-17 19:20（Pacific） |
  | レビュー日 | 2026-08-25 |
  | **レビュー機** | **iPad Air 11-inch (M3)** |
  | 対象 | 1.0 (2) |
  | 指摘 | Guideline 2.1 - Information Needed（NFC機能のデモ動画） |

- Apple が求めている動画の条件は3つ:
  1. **実機**で動く現行バージョン（シミュレータ不可）
  2. アプリと対象ハードウェア（＝NFCタグ）の**初回ペアリング**の様子
  3. そのハードウェアを使う**全ワークフロー**
  さらに「**タグと、実機で動くアプリ画面の両方が映るように撮る**」ことが条件。

### 発生したエラーと解決策

- 症状: NFC機能を確認できないとして 2.1 が返った。
  → 原因(推定): **レビュー機が iPad Air で、iPad には NFC リーダーが無い**。審査員は
  どうやってもタグをかざす確認ができないため、動画を要求してきた（＝アプリの不具合ではない）。
  → 直し方: iPhone 実機＋NTAG213 で動画を撮り、App Store Connect の
  **App Review Information > Notes** に URL を書いて、審査メッセージに返信する。
  - 別案として **iPhone 専用に絞る**（`TARGETED_DEVICE_FAMILY = 1`）手もあるが、
    その場合は build 3 を作り直して再提出になる。**今回は動画対応が正攻法。**

### 次回への引き継ぎ事項・未解決の課題

- **NFCタグは手元にある**（2026-08-26 オーナー確認）。ただし**アプリのNFC機能は
  まだ一度も実機で動かしていない**ので、**動画を撮る作業が、そのまま RELEASE.md の
  「実機が手に入ったら確認すること」チェックリストの消化になる**。
  撮る前に「NFC 利用可」表示と読み取りシートの表示を確認すること
  （ここで失敗したら原因は Developer Portal の **NFC Tag Reading 未設定**＝RELEASE.md の🔴）。
- **提出は iPhone 専用（`TARGETED_DEVICE_FAMILY = 1`）で出している**（`keytag/setup-ios.sh` に明記）。
  それでも審査は iPad Air で行われた＝**iPhone専用アプリの iPad 互換モードで確認された**ため。
  設定ミスではないので直す必要はなく、**返信文にその旨を書くほうが効く**。
- **App Store Connect 上の state は `REJECTED`**（2026-08-26 に `appstore_api.py --review` で確認）。
  文面の分類は "Information Needed" だが、システム上はリジェクト扱いになっている。
  それでも**新ビルドは不要**で、動画リンク＋返信で再開できる（再提出を求められたら build 2 を選び直す）。
- 撮影後の動画は**サブPCへ渡せばフレームを切り出して条件を満たすか確認できる**
  （`imageio-ffmpeg` を 2026-08-26 にサブPCへ導入済み。brew は汚していない）。
- 撮影台本（1本撮り・2〜3分。手元のタグと iPhone の画面が同時に映る角度で固定撮影する）
  1. iPhone のホーム画面から KeyTag を起動 → 右上が「**NFC 利用可**」になるところを映す
  2. **初回ペアリング**: 「タグに書き込む」で未フォーマットの NTAG213 に書き込む
     → 書き込み成功のシートまで
  3. 書いたタグをかざして読み取り → 画面に内容が出る
  4. 鍵を登録 → **貸出** → もう一度かざして **返却** → 台帳に履歴が残るまで
  5. （任意）サーバー連携は「使わなくても全機能が動く」ことを見せるため、**設定しないまま**通す
- 動画の置き場は **YouTube の限定公開**が無難（審査員がログイン不要で見られる）。
- **返信・提出は外部への操作**なのでオーナーの判断で行う（CLAUDE.md 6項）。
- 審査状況の確認は `python3 appstore_api.py --review com.shinsei99.keytag`。

### 返信文のドラフト（動画URLが決まってから Resolution Center で返す）

> Hello,
>
> Thank you for the review. We have added a link to a demo video in the App Review Information
> section (Notes) in App Store Connect.
>
> The video was recorded on a physical iPhone (not a simulator) and shows the NFC tag and the app
> screen at the same time, including: launching the app, writing to a blank NTAG213 tag (initial
> pairing), reading that tag, and the full workflow of registering a key, checking it out, and
> returning it by scanning the tag again.
>
> Please also note that this app is submitted as **iPhone only** (TARGETED_DEVICE_FAMILY = 1).
> The review was performed on an iPad Air 11-inch (M3), which has no NFC reader, so the NFC
> features cannot be exercised on that device. All NFC functionality requires an iPhone with NFC
> tag reading support. The server integration is optional — every feature works entirely
> on-device without it.
>
> Best regards,


## 2026-08-24（メインPC）— KeyTag の審査状況を API で確認（変化なし・待ち）

### 完了したこと

- `python3 appstore_api.py --review com.shinsei99.keytag` で実測。
  **1.0 は `WAITING_FOR_REVIEW`（審査待ち）のまま。提出から7日経過（API上の作成日 2026-08-17）。**
  build 2（2026-08-17 アップロード）は `VALID` ＝受理済みなので、こちらの作業は無い
- ルート `CLAUDE.md` の KeyLine 行に、KeyTag が審査待ちであることを追記
  （これまで一覧には KeyTag の提出が載っておらず、外部公開欄が「—」のままだった）
- ルート `TODO.md` の keyline 行を現状に更新

### 発生したエラーと解決策

- なし（ブラウザ拡張が未接続で App Store Connect の画面自動操作はできなかったが、
  API で同じことが分かるので問題にならなかった）

### 次回への引き継ぎ事項・未解決の課題

- **審査結果を待つだけ。** 見るときは `python3 appstore_api.py --review com.shinsei99.keytag`
- 通ったあとも **NFCタグ到着後の実機検証は未了**（アプリのNFC機能は一度も実機で動かしていない）

---

## 2026-08-18

### 完了したこと

**KeyTag（iOSアプリ）を新規作成し、App Store へ提出した**
- Capacitor 8 + `@capgo/capacitor-nfc`。4画面（読み取り／書き込み／台帳／設定）
- **単体で完結する設計**（サーバー無しで鍵の登録・貸出・返却・台帳が動く）。
  App Store の審査員は社内LANに入れないため、ここが崩れると審査を通らない
- サーバー連携は任意機能。6桁コードでペアリング → Bearerトークン
  （Capacitorは別オリジンでCookieが使えないため）
- `ndef.js` と `ndef.py` がバイト単位で一致することをテスト化（`test_ndef_parity.py`）
- 1.0.0 / **build 2** で提出。サポート・プライバシーポリシーを gh-pages に公開

**KeyLine 本体の追加**
- 物件名称と、鍵番号ごとの本数（`migrations/002`）
- 連続登録画面（`/register`）とアプリ用API（`/api/register` `/api/asset`
  `/api/checkout` `/api/return` `/api/pair` `/api/ping`）
- アプリ連携画面（`/devices`）。端末紛失時はここで即解除できる

### 発生したエラーと解決策

1. **アップロードが 90778 で弾かれた**
   `Invalid entitlement ... 'NDEF is disallowed'` →
   原因: 新しいSDK（26.5）では `com.apple.developer.nfc.readersession.formats` に
   **NDEF を入れられない** → 直し方: `['TAG','NDEF']` を **`['TAG']`** に。
   TAGセッションからNDEFの読み書きもできるので機能は落ちない。
   `setup-ios.sh` にも反映済みなので作り直しても再発しない

2. **`DistributionAppRecordProviderError error 0`**
   症状: Distribute で落ちる → 原因: App Store Connect にアプリ登録が無かった。
   登録後も Xcode のキャッシュが古く「新規作成」を試みて
   「SKU/BundleID/名前が既に使われている」と自分自身とぶつかっていた →
   直し方: **Xcodeを再起動**

3. **スクショの寸法が弾かれた**
   iPhone 17 Pro Max の 1320×2868 は6.9インチ枠用。6.5インチ枠は **1284×2778**。
   `sips -z 2778 1284` で変換（記録どおりの現象。`reference_appstore_screenshot_sizes`）

4. **アプリ名 `KeyTag` が取得できなかった**
   同名アプリが既存（深圳市立显通科技有限公司）→ **掲載名は `KeyTagNFC`**、
   ホーム画面の表示名は `KeyTag` のまま（一意性の制約は掲載名だけ）

5. **`ios-build-guard.sh` が壊れていた**
   `$MAX_ARCH。` のように変数の直後に日本語が続くと、bashが「。」の先頭バイトを
   変数名に取り込み `unbound variable` で落ちる。**成功パスで必ず落ちていた**ため、
   「衝突なし」の判定が一度も出せていなかった。`${VAR}` 形式に修正

6. **別アプリのビルドをシミュレータに入れていた**
   DerivedData に `App` という名のプロジェクトが3つある（Capacitorアプリは全部
   プロジェクト名が `App`）→ `-derivedDataPath` で出力先を明示して解決

7. **`sqlite3.executescript()` の暗黙COMMIT / 時刻だけでは履歴の全順序が決まらない**
   （詳細は 2026-08-17 の節）

### 次回への引き継ぎ事項・未解決の課題

**🔴 最優先：NFCタグ到着後の実機検証**
アプリのNFC機能は**一度も実機で動かしていない**（タグと実機が無いため）。
確認項目は `keytag/RELEASE.md` のチェックリスト。特に:
- 右上が「NFC 利用可」になるか
- **まっさらなタグでUIDが読めるか**（TAGエンタイトルメントの確認）
- NTAG213 に書けるか
- 平文 `http://192.168.1.105:8534` へ繋がるか（ATS例外の確認）

**KeyLine 本体（サーバー側）**
- 平文httpでiOSのバックグラウンドタグ読み取りが動くかは**未検証のまま**。
  ただし**アプリ内で貸出まで完結するようになったので、依存はしていない**
- 常駐登録（`_launchd/install.sh`）は**まだ実行していない**
- 利用者の追加・パスワード変更の画面が無い（`seed.py` と CLI のみ）

**KeyTag（アプリ）**
- 審査の結果待ち。リジェクトされたら build を +1 して出し直す
  （`./ios-build-guard.sh keyline/keytag --bump`）
- 次に触るときは `keytag/store-text.md`（掲載文言）と `keytag/RELEASE.md`（手順）を見る

# SESSION_LOG — KeyLine

## 2026-08-17

### 完了したこと

**Phase 0（現状確認）**
- KeyLine は新規。既存コードなし。Flutter / React Native / Expo / Android SDK / Java /
  Supabase CLI / Docker が**すべて未導入**であることを実測で確認
- 既存の iOS 配信実績6本はすべて Capacitor + Web（Team ID `773DPMVW7Q`）

**方針決定（対話で確定）**
1. Android は対象外、**iOS のみ**
2. SaaS をやめ、**社内LAN限定の社内ツール**。本体はメインPC（192.168.1.105:8534）
3. NFCは「**タグにURLを書く**」方式（iOSバックグラウンドタグ読み取り）。アプリ導入不要
4. 鍵ボックス横に**鍵管理用スマホ1台**（共用）。Safariで開くだけ
5. **社外（業者・内見客）にも貸す**ため、「操作する人（users）」と「借りる人（borrowers）」を分離
6. 操作した社員は**記録しない**（共用端末・現場で1タップ減らす）
7. OCR は `claude` CLI のビジョン。**画像は返却から30日で自動削除**

**Phase 1（DB）** — `migrations/001_init.sql`
- テーブル7・インデックス18・トリガー9・ビュー2
- 二重貸出を3層（BEGIN IMMEDIATE / 条件付きUPDATE+changes() / 部分UNIQUEインデックス）で防止
- 組織またぎの参照をトリガーで遮断（Postgres+RLS が無い分をここで担保）
- テスト61件すべて成功

**Phase 2〜5（アプリ本体）**
- 認証（PBKDF2 480,000回・sessionsテーブル・Cookie 365日）
- 貸出画面／返却画面／未登録タグ登録／貸出先の選択・新規作成・OCR
- 管理画面（ダッシュボード・一覧・詳細・履歴・ボックス・貸出先・強制返却・タグ発行/交換）
- SSE によるリアルタイム更新
- 画像の自動削除（`purge.py` ＋ launchd 毎日3:30）
- 通しテスト35件すべて成功。**ブラウザで実際に表示して目視確認済み**
- OCR を合成した名刺で実測 → 13秒・氏名/会社名/携帯番号を正しく抽出

### 発生したエラーと解決策

1. **`cannot commit - no transaction is active`**
   症状: マイグレーションが失敗 → 原因: `sqlite3.executescript()` は**実行前に暗黙のCOMMIT**を
   発行するため、外側の `BEGIN` が消える → 直し方: `BEGIN`/`COMMIT` を**スクリプト文字列の中**に
   書いて `executescript` に渡す。適用記録のINSERTも同じスクリプトに入れて原子性を保つ

2. **履歴の最新1件を取り違える**
   症状: 強制返却のテストが落ちる → 原因: 同一秒に貸出が2件入り `ORDER BY checkout_at` の順序が
   決まらない。**ミリ秒精度に上げても同一ミリ秒に2件入るので解決しない** →
   直し方: `ORDER BY checkout_at DESC, rowid DESC`。時刻だけでは全順序を保証できない。
   ミリ秒精度自体は監査記録として有用なので残した（※秒精度と混ぜると文字列比較が壊れる）

3. **タグURLに `127.0.0.1` が出る**
   症状: 詳細画面のタグURLがアクセス中のホストになる → 原因: `request.base_url` を使っていた →
   直し方: `services.lan_base_url()` が常にLANのIPを返す。`run.sh` が en1（.105）を明示。
   **タグは物理的に書き直しになるため、実機検証前に潰せたのは大きい**

4. **`command not found: curl`（テスト中）**
   症状: シェルのループ以降すべてのコマンドが消える → 原因: zsh の `path` は `PATH` に連動する
   **特殊変数**で、`for path in ...` が PATH を破壊していた → 直し方: 変数名を変える

5. **現場画面にPC用ナビが出て場所を食う**
   → `/t/…` の画面だけ `{% set slim = true %}` で最小ヘッダーにした
   （Jinjaの継承で子の `set` が親に伝わることは実測で確認）

### 次回への引き継ぎ事項・未解決の課題

**🔴 最優先（NFCタグ到着後すぐ）**
平文 `http://192.168.1.105:8534/t/<token>` を、iOSのバックグラウンドタグ読み取りが
開いてくれるか**未確認**。事例の多くは https の公開URL。
- 検証: タグ1枚にURLを書いて iPhone(XS以降) でかざす。5分で白黒つく
- 黒だった場合の代替（調査済み・行き止まりではない）:
  1. `keyline.daikyocorp.co.jp` の A レコードを 192.168.1.105 に向け、DNS-01 で
     Let's Encrypt 証明書 → LAN内でも正規HTTPS（ドメインは自社保有）
  2. 自己署名証明書＋各iPhoneに構成プロファイル（端末ごとに1回の手作業）
- HTTPS化したら `app.py` の `set_cookie` に `secure=True` を付けること

**未着手**
- 利用者（users）の追加・パスワード変更の画面。いまは `seed.py` と CLI のみ
- 返却期限の通知（Chatwork/LINE）。ご指示30で将来拡張とされているもの
- 常駐登録（`_launchd/install.sh`）は**作ったが未実行**。実機検証が通ってから登録する

**判断が要る点**
- 鍵管理スマホを紛失したときの手順（`sessions` の行を消せば即座に無効化できる）を
  運用として決めておく必要がある
