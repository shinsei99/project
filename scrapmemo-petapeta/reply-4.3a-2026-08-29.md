# スクラップメモpetapeta 1.0.5 — 再提出のときに付ける一言（2026-08-29 用意）

**いつ**: 週明け以降（オーナー判断）。**KeyTag の返信を先に送ってから**にする。
**どこに**: App Store Connect →「App Review」→ 該当の提出 → **Resolution Center に返信**してから
「審査へ提出」。**★返信なしの再提出はしない**（8/28 に KeyTag がそれで同じ定型文を返された）。

**前提（2026-08-29 に API で実測）**

- `1.0.5` = `REJECTED` ／ `1.0.4` = `READY_FOR_SALE`。**更新が弾かれても配信中の版は無事**
- ビルド **9 が `VALID` でひも付け済み**。「今回の変更」も記入済み ＝ **作り直し不要。出すだけ**

**書き方の方針**: **短く、反論せず、事実だけ**。このアプリは 1.0.1〜1.0.4 の**4回とも審査を
通っている**。長い弁明より「配信中アプリの不具合修正である」という一点のほうが強い。

---

## 送る文面（英語・そのままコピー）

```
Hello,

This is an update to an app that is already on the App Store. Version 1.0.4 is live now, and
versions 1.0.1 through 1.0.4 were each approved by review.

Version 1.0.5 contains one change: in the note editor, the Done and Cancel buttons were at
the bottom of the note, so with a long note the user had to scroll through several screens to
reach them, and taps outside the editor discarded the edit. We moved those two buttons to the
header. There are no new features, no new frameworks or SDKs, and no changes to the app
concept or to the store listing.

We understand that the 4.3(a) decision may concern our account as a whole rather than this
update. We have stopped submitting new apps, and we have deleted one unreleased app from App
Store Connect. We are glad to answer any questions about our other apps.

If this update cannot proceed as submitted, please let us know what to change.

Best regards,
Shinichi Washimi
```

## 日本語（内容確認用・送るのは上の英語）

```
これは、すでに App Store で配信しているアプリの更新です。現在 1.0.4 が配信中で、
1.0.1 から 1.0.4 まで、いずれも審査を通っています。

1.0.5 の変更は1点だけです。メモの編集画面で「完了」と「キャンセル」が本文の一番下に
あったため、長い文章では何画面もスクロールしないと押せず、編集画面の外をタップして
編集が破棄されてしまうことがありました。この2つのボタンをヘッダーへ移しました。
新機能の追加はなく、新しいフレームワークやSDKの追加もなく、アプリのコンセプトや
ストア掲載情報の変更もありません。

4.3(a) のご判断が、この更新ではなく私たちのアカウント全体に関するものである可能性は
理解しています。新規アプリの提出は止めており、未配信だったアプリ1本は App Store
Connect から削除しました。ほかのアプリについてのご質問にも喜んでお答えします。

この更新をこのままでは進められない場合は、何を変更すればよいかお知らせください。
```

---

## 送ったあと

- 結果の見方: `python3 ../appstore_api.py --review com.shinsei99.scrapmemo`
- **通れば**: アカウントの札が外れた可能性が高い。次を1本だけ、間隔を空けて出す判断材料になる
- **また同じ定型文なら**: 個別のアプリの話ではないことが確定する。
  → ゲーム5本を1本に統合する案へ進む（App の本数を減らすのが 4.3(a) への直接的な答え）
- **どちらでも 1.0.4 は配信中のまま。** 焦って何度も出し直さないこと（バースト提出が今回の原因）
