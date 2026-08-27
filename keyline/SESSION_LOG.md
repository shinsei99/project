## 2026-08-28（メインPC）— **Guideline 4.3(a)（スパム）でリジェクト**。名前・見せ方を作り直し、build 4 を上げた

### 何が起きたか

2.1（NFCのデモ動画を出せ）に動画で回答して再提出 → 審査は進んだが、
今度は **Guideline 4.3(a) — Design: Spam** でリジェクト。

> 他の開発者が App Store に出しているアプリと、バイナリ・メタデータ・**コンセプト**が
> 似ていて、違いがわずかしかない

### ★調べて分かったこと — 「似ている相手」は NFCツールではなく**量産の台帳アプリ**

最初は「NFCユーティリティ（NFC Tools 系）の棚に見えたのだろう」と考えたが、
**iTunes Search API で実際に調べたら見当違いだった。**

`hao du` という開発者が、**同じ型で量産した台帳アプリ**を多数出している。

```
鍵台帳-貸出返却管理2026        ★賃貸キー受渡し台帳2026        工具貸出台帳 在庫返却管理2026
来訪者パス台帳・貸出返却2026     貸出台帳-物品貸出管理2026       証照貸出台帳2026
レンタル台帳2026               封印台帳 シール番号記録2026      文書保存箱ラベル管理2026
```

とくに **「賃貸キー受渡し台帳2026」** の説明文は

> 大家、不動産仲介、アパート管理者、物件管理スタッフ向け。物件ごとに鍵ファイルを作成し、
> **鍵番号、数量**、保管者、受渡し日、返却状況を記録。**未返却や数量不一致の一覧**、
> 履歴検索、PDF書き出し。ログイン不要、ネット接続不要、端末内のみ。

で、**KeyTag と対象も機能もほぼ同じ**。4.3 はこの系統を指していると考えるのが自然。

**そして決定的な違いは、これらが NFC を使わないこと**（説明文に NFC の語が一切無い。
すべて手入力・端末内完結）。つまり **NFC は捨てるべきものではなく、差別化の中心**だった。

> ⚠️ **この調査をする前に「名前から NFC を外し、台帳を前面に」と助言していたが、方向が逆だった。**
> 「◯◯台帳」に寄せると、上の量産群と同じ棚に並ぶ。**次に同種の判断をするときは、
> 必ず先に App Store を実測すること。**

### 完了したこと

- **掲載名を `KeyTagNFC` → `KeyTag鍵管理` に変更**（jp/us とも空きを実測）。
  ホーム画面の表示名（`CFBundleDisplayName`）は `KeyTag` のまま
- **`keytag/store-text.md` を全面改訂**。サブタイトルの冒頭を「NFC」から「鍵」へ。
  説明文に **「ほかの貸出台帳アプリとの違い」** の節を新設。
  **副カテゴリ（ユーティリティ）を外す**判断（NFC Tools の棚を離れ、かといって
  「仕事効率化」＝量産台帳群の棚にも行かない。主＝ビジネスのみ）
- **審査ノートに 4.3(a) への回答を明記**（テンプレート不使用・相違点3つ・確認方法）
- **★サーバー連携を「公開仕様」にした**（量産台帳アプリが持っていない差別化点）
  - `keytag/server-api/keytag-server.py` … **参照実装**。標準ライブラリだけ・1ファイル・
    追加インストール不要。`python3 keytag-server.py` で起動し、6桁コードでペアリングできる
  - `keytag/server-api/API.md` … 公開仕様（6エンドポイント・認証・タグURL形式・データ構造）
  - **gh-pages に公開**（`keytagnfc-support/api.html` と `keytag-server.py`）。
    サポートページに「複数人で同じ台帳を共有する」の節を追加。**公開URLの200を実測**
  - アプリの設定画面からこの仕様ページへ**リンクを追加**（審査員がその場で辿れる）
- **build 4 を Archive → アップロード → `VALID` を API で確認**
  （`ITSAppUsesNonExemptEncryption=false` がバンドルに入っていることも実測。
   build 3 で踏んだ輸出コンプライアンス待ちは今回起きないはず）

### 参照実装の動作確認（実測）

```
ペアリング → トークン取得                      ✅
鍵を登録 → タグに書くURLを発行                 ✅ http://…/t/16988f8dc0f55215
かざす → 状態を取得                            ✅ 保管中 / 10001 / 10003 ×3（計4本）
貸出                                           ✅ 見本 花子（業者）返却予定 18:00
二重貸出をサーバー側で拒否                      ✅「この鍵はすでに貸出中です」
返却 → 貸出先が候補に残る                       ✅
ブラウザで台帳の一覧 / タグURLのページ           ✅ どちらも画面で確認
```

### 発生したエラーと解決策

- **症状**: `./simtap.py calib` が失敗し、シミュレータを操作できない。
  **原因**: Simulator.app のプロセスは動いているが**ウインドウが0枚**
  （`System Events` で `count of windows` = 0）。`open -a Simulator --args -CurrentDeviceUDID …`
  でも変わらず。アクセシビリティ権限は生きている（プロセス一覧は取れる）。
  **未解決。** そのため**スクリーンショットの撮り直しができていない**（下記）
- gh-pages への push が fast-forward で弾かれた → 別アプリの自動デプロイが先に入っていた。
  `git pull --rebase` で解決（自分の変更は `keytagnfc-support/` だけなので競合なし）

### 次回への引き継ぎ事項・未解決の課題

- **★スクリーンショットが未着手**（`store-text.md` に並び順だけ決めてある）。
  シミュレータのウインドウが出ないので、**実機で撮るのが早い**。並びは
  ①かざして鍵が特定された画面 ②台帳 ③貸出 ④タグに書き込む ⑤サーバー連携 の順
- **デモ動画は作り直さない判断**。当初は「台帳から始まる版にする」と考えたが、
  上の調査で **NFC こそが差別化点**と分かったため、**NFCの読み書きを見せている
  いまの動画のほうが 4.3 に効く**（量産台帳アプリには撮れない絵だから）。
  足すなら「サーバー連携で複数人が同じ台帳を見る」場面。これは実機とタグが要る
- **ASC 側のメタデータ入力と提出は未実施**（名前・サブタイトル・説明文・キーワード・
  カテゴリ・審査ノート・スクショ）。文言は `keytag/store-text.md` にそのまま入れられる形である
- **新しい App 記録は作らないこと。** 4.3 の直後に似た中身で別記録を作るのは、
  Apple がスパムとして探しているパターンそのもの（通知文にも明記されている）。
  未配信なので、いまの記録のまま名前もカテゴリも変更できる

## 2026-08-27（メインPC）— デモ動画を作って公開し、**build 3 で再提出まで完了**

### 完了したこと

- **再提出まで到達。`WAITING_FOR_REVIEW` / build 3（VALID）を API で確認した。**

**① 実機での検証は「動画そのもの」で済んだ**

オーナーが TestFlight の build 3 で撮影。動画の中で **タグへの書き込みが成功し、読み取りも通っている**。
build 2 ではこの2つは必ず失敗する（`stopScanning` が `currentTag` を null にするため書き込みは
`No active NFC session or tag`、まっさらなタグは `Failed to read NDEF message`）。
**＝ 8/26 のNFC修正が実機で効いていることの証拠**。`RELEASE.md` の
「実機が手に入ったら確認すること」の主要項目は、これで消化した。

**② GoPro からの取り込み（はまった点）**

- **HERO9 は MTP 接続なので `/Volumes` にマウントされない**（`ioreg -p IOUSB -l | grep "USB Product Name"`
  では見える）。取り込みは **イメージキャプチャ.app** を使う。カードリーダーでもよい
- 最初に入ったのは **`GL010203.LRV`＝低解像度プロキシで、しかも別件の私的な映像**だった。
  GoProは連番で、**`GX`＝本編 / `GL`＝プロキシ**。**番号が最大のものを選ぶ**。
  カードの日付が壊れている（`4月12日 2262年` と出た）ので**日付順の並べ替えは当てにならない**
- 本編は **`GX010219.MP4`（1分57秒・2704×1520・HEVC・628MB）**。メインPCの `~/Pictures/` にある

**③ 動画の仕上げ — このMacだけで完結した**

**★`TODO.md` の「メインPCに ffmpeg が無いのでサブPCへ渡すのが早い」は誤りだった。**
`agent-platform/.venv` の **imageio-ffmpeg 同梱バイナリ（ffmpeg 7.1）**があり、
**libass / libfreetype / libharfbuzz / libx264 入り**なので日本語字幕の焼き込みまでできる。
gTTS・moviepy も同じ venv にある。**サブPCへ渡す必要はなかった**ので TODO を訂正した。

| 項目 | 内容 |
|---|---|
| 完成品 | 1分59秒 / 1280×720 / H.264 / **20.0MB** / faststart |
| 字幕 | **英語＝画面上・日本語＝画面下**（下に4行まとめるとiPhoneが隠れるため分けた）。Hiragino Sans W6 |
| 音声 | **元音声は不使用**（`-map 0:v:0`。事務所の会話が入る恐れがあるため）＋ gTTS の日本語ナレーション13カット |
| 手順 | `keyline/keytag/build-demo-video.py`（新規・git入り）。出力は `.demo-build/`（gitignore） |

ffmpeg が無いと思っていた間に書いた **`scratchpad/vidinfo.swift`**（AVFoundation で尺・解像度・
コーデックを読み、フレームを切り出す）も有効だった。**Xcode があれば `swift` 一発で動く**ので、
ffmpeg が無いMacで動画を調べるときに使える。

**④ 公開とApp Store Connect**

- gh-pages の `keytagnfc-support/` に動画とポスターを追加し、**イントロ直後**に埋め込んだ
  （審査員がすぐ見つけられる位置）。英語の説明文も併記。コミット `93c7eb1c`
- 公開URLを実測: ページ 200 / **`keytag-nfc-demo.mp4` 200・21,008,539バイト・`video/mp4`** /
  ポスター 200。**GitHub Pages への反映に45秒かかった**（push直後は404が返る）
- **バージョン 1.0 には build 2 がひも付いたままだった**ので、API で build 3 に差し替えた
  （`PATCH /v1/appStoreVersions/{id}/relationships/build` → 204）。
  **これで状態が `REJECTED` → `PREPARE_FOR_SUBMISSION` に変わった**（＝画面の赤い警告も消える）
- **App Review Information の Notes**（`PATCH /v1/appStoreReviewDetails/{id}`）に
  動画URL・iPhone専用の説明・デモアカウント不要を記載（1,444文字）
- オーナーが Resolution Center へ返信し、**審査に提出 → `WAITING_FOR_REVIEW`**

### 発生したエラーと解決策

- 症状: `.gitignore` に `keyline/keytag/.demo-build/   # コメント` と書いたら効かなかった
  （`git check-ignore -v` が `!keyline/**` を返した）。
  → 原因: **`.gitignore` は行末コメントに対応していない**。`#` は行頭のみ。
  パターンが `…/.demo-build/   # デモ動画…` という文字列そのものになっていた。
  → 直し方: コメントは前の行に独立させる。**`git check-ignore -v` で必ず確かめる**
  （直下の `.gitignore` は1行目から `*` で全無視 → `!` で個別許可する方式なので、
  ここを間違えるとファイルが黙って git に入らない）。

### 次回への引き継ぎ事項・未解決の課題

- **審査結果待ち。** `python3 appstore_api.py --review com.shinsei99.keytag` で追う。
  今回は「情報が足りない」への回答なので、通れば次は配信。
- **元動画 `~/Pictures/GX010219.MP4`（628MB）はメインPCにしかない**（git管理外）。
  動画を作り直すときはこれが要る。消さないこと。
- **`~/Pictures/GL010203.LRV` は別件の私的な映像**（イメージキャプチャで誤って取り込んだもの）。
  不要なら消してよい。
- 動画は **public リポジトリの gh-pages にある**＝誰でも落とせる。中身はダミーデータのみで
  確認済みだが、**force push しない方針なので履歴から実質消せない**ことは意識しておく。
- 未消化: 動画の最後の3秒がホーム画面に戻っている（内容の誤りではない。気になるなら
  112.5秒で切って静止させれば直る）。

## 2026-08-26（メインPC）— 実機で「Failed to read NDEF message」→ **原因はバグ2件**。修正した

### 完了したこと

- オーナーが TestFlight の build 2 でタグをかざしたところ
  **「failed to read NDEF message …NDEF tag…」** でシートが赤くなった、との報告。
  **アプリ側のバグ2件**を特定し、`www/app.js` を修正した。**タグの不良でも実機の問題でもない。**

**バグ①（今回のエラーそのもの）— プラグインのオプション名が違う**

`scanOnce()` が `sessionType: 'tag'` を渡していたが、`@capgo/capacitor-nfc` 8.2.3 の
正しい名前は **`iosSessionType`**（`dist/esm/definitions.d.ts:121` / `NfcPlugin.swift:124`
`call.getString("iosSessionType", "ndef")`）。**知らないキーは黙って捨てられ、既定の
`ndef` セッションになる**＝ `NFCNDEFReaderSession` で動いていた。

その経路（`NfcPlugin.swift:553-562`）は、まっさら（NDEF未フォーマット）のタグで
`readNDEF` がエラーになると
`session.invalidate(errorMessage: "Failed to read NDEF message: \(readError.localizedDescription)")`
を呼ぶ。iOSの `localizedDescription` は「NDEF tag does not contain any NDEF message」なので、
**オーナーが見た文言と一致する**。
TAGセッション（`processTag`）なら `message == nil` のとき `emitTagEvent` でUIDだけ返して続行するので、
この失敗は起きない。

**バグ②（まだ誰も踏んでいないが、書き込みが必ず失敗する）**

`scanOnce()` は検出直後に `Nfc.stopScanning()` を呼んでいた。`stopScanning` は
**セッションを invalidate したうえで `currentTag = nil` にする**（`NfcPlugin.swift:200-209`）。
その後に `Nfc.write()` を呼んでも
`guard currentTag != nil else { call.reject("No active NFC session or tag…") }` で必ず落ちる。
`invalidateAfterFirstRead: true` も同じ向きに効く。
**iOSは「タグに繋がっている同じセッションの中」でしか書けない。**

→ 修正: `scanOnce(msg, {keepOpen:true})` を足し、書き込み時はセッションを開いたまま
`Nfc.write()` し、`finally` で `closeScan()` する。読み取り側は今までどおり1回で閉じる。

**★この2件は、審査に出した build 2 の実体に入っている**（推測ではない）。
`~/Library/Developer/Xcode/Archives/2026-08-18/KeyTag 2026-08-18 11.10 build2.xcarchive/
Products/Applications/App.app/public/app.js` を直接見て確認した
（`CFBundleVersion=2` / 74行目 `sessionType: 'tag'` / 66行目 `stopScanning()`）。
**つまり build 2 では「まっさらなタグは読めない」「タグに書けない」。**

### 発生したエラーと解決策

- 症状: 実機でタグをかざすと `Failed to read NDEF message: NDEF tag does not contain any NDEF message`
  → 原因: 上のバグ①（`sessionType` ではなく `iosSessionType`。誤ったキーは無視され既定のNDEFセッションになる）
  → 直し方: `www/app.js` の `scanOnce()` で `iosSessionType: 'tag'` を渡す。
- **App ID の NFC Tag Reading は有効だった**（2026-08-26 に API で確認済み）ので、
  `RELEASE.md` の🔴は今回の原因ではなかった。**先に潰しておいたのが効いて、切り分けが早かった。**

### 検証（実機以外でできる範囲）

- `node --check` で `app.js` / `ndef.js` とも構文OK
- `python3 -m http.server 5180 --directory www` ＋ `./va.sh` で実際に開いた:
  - `/` `style.css` `app.js` `ndef.js` すべて **200**、**JSエラー0件**（favicon の404のみ）
  - 「書き込み」タブ → 鍵の名称を入れて「タグに書き込む」→
    **⚠️ NFCの読み書きは実機でのみ動作します（いまはブラウザ表示）** が出る＝ハンドラは通っている
- **NFCの実挙動は実機でしか確かめられない。ここは未検証。**

### 次回への引き継ぎ事項・未解決の課題

- **build 3 を作ってアップロードした（2026-08-26 15:49・オーナーの指示）。**
  オーナーの選択は「実機での事前確認を挟まず、いきなり build 3 を上げる」。
  - `npx cap sync ios` → `./ios-build-guard.sh keyline/keytag --bump`（2→3・`version.json` も更新）
  - `xcodebuild archive`（クラウド署名なので ASC の API キーを渡す。手順は
    `photo-remake/SESSION_LOG.md` 2026-08-26 と同じ）→ **ARCHIVE SUCCEEDED**
  - `xcodebuild -exportArchive`（`destination=upload`）→ **Upload succeeded / EXPORT SUCCEEDED**
  - アーカイブの中身を実測: `CFBundleVersion=3` / `public/app.js` に `iosSessionType` と
    `keepOpen` が入っている / entitlement は `["TAG"]` / Team `773DPMVW7Q`
  - **処理後 `VALID`**。TestFlight の「社内テスト」グループに build 3 が入ったことを API で確認
- **★踏んだ罠: build 3 が TestFlight に出てこなかった（オーナーから「1.0.0 は表示されてる」）。**
  原因は **`internalBuildState = MISSING_EXPORT_COMPLIANCE`**＝輸出コンプライアンス未回答。
  `Info.plist` に `ITSAppUsesNonExemptEncryption` が無いと**毎回ASCで聞かれ、回答するまで
  TestFlight に一切出ない**（build 2 は提出時にオーナーが画面で答えていた）。
  → `PATCH /v1/builds/{id} {"usesNonExemptEncryption": false}` で解除 → **`IN_BETA_TESTING`**。
  暗号は使っていない（通信は社内LANの平文HTTPのみ・暗号APIの呼び出し0件を grep で確認）ので
  `false` が正しく、**build 2 の既存の宣言とも一致**する。
  → 再発防止に **`Info.plist` と `setup-ios.sh` の両方に `ITSAppUsesNonExemptEncryption=False` を入れた**
  （※すでに上げた build 3 には効かない。次のビルドから）
- **残り: ③ build 3 を実機で動かして NFC が直ったことを確認 → ④ デモ動画 →
  ⑤ Resolution Center へ返信（動画URL＋『不具合を修正した build 3 を添付した』）。**
  ⑤は外部への操作なのでオーナーの手で。
- Archive・アップロード・審査への返信は**外部への操作**なのでオーナーの判断で（CLAUDE.md 6項）。
- build を上げるときは `./ios-build-guard.sh keyline/keytag --bump` ＋ `npx cap sync ios` を忘れない。
- **`www/` を直したら `npx cap sync ios` をしないと `ios/App/App/public/` は古いまま**
  （今回まさにそこを見て build 2 の中身を確認した）。

## 2026-08-26（メインPC）— KeyTag を実機に入れる道を用意した（TestFlight 内部テスト）

### 完了したこと

- **オーナーから「NFCアプリをスマホに入れたい」。デモ動画撮影の前提なので TestFlight で用意した。**
- App Store Connect API で実測して分かったこと:

  | 調べたこと | 結果 |
  |---|---|
  | build 2 の状態 | `VALID` / `expired=false` / 期限 **2026-11-15** / `usesNonExemptEncryption=false`（輸出コンプライアンス回答済み）＝**そのまま配れる** |
  | TestFlight グループ | **1つも無かった**（`betaGroups` が空）。だから iPhone から落とせなかった |
  | **App ID の NFC ケーパビリティ** | 🟢 **`UKQ5NC8UC5_NFC_TAG_READING` が有効**（`GET /v1/bundleIds?...&include=bundleIdCapabilities`）。`RELEASE.md` の🔴「未設定だとタグを読んだ瞬間に必ず失敗する」は**解消済み**と確認し、RELEASE.md を ✅ に書き換えた |
  | チームユーザー | `s.washimi@icloud.com`（ACCOUNT_HOLDER/ADMIN）の1名のみ＝内部テスターにできるのはこの人だけ |

- **オーナーの許可を得たうえで**（外部への操作なので CLAUDE.md 6項に従い確認した）、API で:
  1. 内部テストグループ **社内テスト**（`b9115212-26cf-44d5-97a0-0c5130be91aa`・`isInternalGroup=true`・`hasAccessToAllBuilds=true`）を作成
  2. テスター `s.washimi@icloud.com` を招待 → **`state=INVITED`**
  3. グループから build 2 が見えることを確認（`GET /betaGroups/{id}/builds` に該当 id）
- 手順は `keytag/RELEASE.md` に「実機に入れる方法 — TestFlight（内部テスト）」として残した。

### 発生したエラーと解決策

- 症状: `POST /betaGroups/{id}/relationships/builds` が **422 `Cannot add internal group to a build.`**
  → 原因: グループを **`hasAccessToAllBuilds=true`** で作ったため、**個別の build 割り当ては
  そもそも受け付けない**（全ビルドが自動で流れる仕様）。エラーだが実害なし。
  → 確認: `GET /betaGroups/{id}/builds` に build 2 が入っていることを実測。**対処不要**。

### 次回への引き継ぎ事項・未解決の課題

- **iPhone 側の操作はオーナーの手**: App Store から TestFlight を入れる → 招待メールの
  `View in TestFlight` → KeyTagNFC をインストール。
- 入ったら **`RELEASE.md` の「実機が手に入ったら確認すること」の上4つ**（NFC利用可 / 読み取りシート /
  未フォーマットのタグでUID / NTAG213へ書き込み）を先に通す。**ここが通れば、そのまま
  差し戻し対応のデモ動画の撮影に入れる**（台本は下の 2026-08-26（サブPC）の節と直下 `TODO.md`）。
- **撮影前に集中モードON・ホーム画面の映り込み対策**（動画は public に置く可能性がある）。
- **審査中の提出物には影響していない**（TestFlight配布と審査は別系統）。状態確認は
  `python3 appstore_api.py --review com.shinsei99.keytag`。

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
