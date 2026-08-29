# スクラップメモpetapeta 1.0.5 — 4.3(a) への返信（2026-08-29）

**送り先**: https://appstoreconnect.apple.com/apps/6793374853/distribution
→ 左メニュー「**App Review**」→ 該当の提出 → **「App Reviewに返信」**（メッセージ本文の下）

**★KeyTag に送った文面とは別の内容にしてある。** 同じ文章を2本に送ると
「やはり同じ型で量産している」という最初の指摘を補強してしまう。
こちらは**このアプリ固有の事実**（配信中・UI修正だけ・4回とも審査を通っている）を主役にする。

**前提（2026-08-29 実測）**

- `1.0.5` = `REJECTED` ／ `1.0.4` = `READY_FOR_SALE`。**更新が弾かれても配信中の版は無事**
- ビルド **9 が `VALID` でひも付け済み**。「今回の変更」も記入済み ＝ **作り直し不要**
- にゃんこのアイス屋さんの App 記録は **削除済み**（同日実施）

---

## 送る文面（英語・そのままコピー）

```
Hello,

Thank you for the review. This is an update to an app that is already on the App Store.
Version 1.0.4 is live, and versions 1.0.1 through 1.0.4 were each approved by review.

Version 1.0.5 contains one change: in the note editor, the Done and Cancel buttons were at
the bottom of the note, so with a long note the user had to scroll through several screens
to reach them, and tapping outside the editor discarded the edit. We moved those two buttons
to the header. There are no new features, no new frameworks or SDKs, and no changes to the
app concept or to the store listing.

We think we understand what happened. We submitted three unrelated items within about six
hours on August 27-28: a resubmission of one app, this bug-fix update, and a new app. They
were separate projects at separate stages, and we submitted them together simply because
they happened to be ready on the same day. We now see how that looks from the outside, and
it was our mistake in scheduling rather than repackaging.

What we have done since:

- We deleted the new app ("にゃんこのアイス屋さん", com.daikyo.nyankoice) from our account.
  It will not be resubmitted.
- We have stopped submitting new apps. Four other apps that were ready have been withheld.
- From now on we will submit one item at a time and wait for the result before the next one.

We would like to start with this update. We are resubmitting version 1.0.5 now, and we ask
that you review it. We will wait for your decision on it before we resubmit anything else,
including KeyTag. We are not planning any other submissions.

If anything in this update needs to change, please tell us and we will fix it.

Best regards,
Shinichi Washimi
```

## 日本語（内容確認用・送るのは上の英語）

```
ご確認ありがとうございます。これは、すでに App Store で配信しているアプリの更新です。
1.0.4 が配信中で、1.0.1 から 1.0.4 まで、いずれも審査を通っています。

1.0.5 の変更は1点だけです。メモの編集画面で「完了」と「キャンセル」が本文の一番下に
あったため、長い文章では何画面もスクロールしないと押せず、編集画面の外をタップして
編集が破棄されてしまうことがありました。この2つをヘッダーへ移しました。新機能の追加も、
新しいフレームワークやSDKの追加も、コンセプトや掲載情報の変更もありません。

何が起きたのかは分かったつもりです。8月27〜28日の約6時間のあいだに、関係のない3件を
提出しました（1本の再提出、この不具合修正の更新、そして新規アプリ）。それぞれ別の
プロジェクトで、進み具合もばらばらでしたが、たまたま同じ日に準備ができたので一緒に
出してしまいました。外から見てどう見えるか、いまは理解しています。作り直しや使い回しでは
なく、こちらの段取りの誤りでした。

そのあとに行ったこと:
・新規アプリ（にゃんこのアイス屋さん）はアカウントから削除しました。再提出しません
・新規アプリの提出は止めました。準備できていた他の4本も出さずに保留しています
・今後は**1件ずつ提出し、結果が出てから次に進みます**

まずはこの更新から再開させてください。**1.0.5 をいま再提出しますので、審査をお願いします。**
その結果が出るまで、KeyTag を含め、ほかのものは再提出しません。ほかに提出の予定もありません。

この更新に直すべき点があれば、教えていただければ直します。
```

---

## 送ったあとの段取り（★同時に出さない）

| 順 | やること |
|---|---|
| 1 | この返信を送る（**文中で「いま再提出します」と書いているので、間を空けない**） |
| 2 | **1.0.5 を審査へ提出**（1件だけ・返信の直後に） |
| 3 | 結果を見る `python3 ../appstore_api.py --review com.shinsei99.scrapmemo` |
| 4 | **通ってから** KeyTag を再提出（`../keyline/keytag/`） |

**★2と4を同じ日にやらない。** 短期間に複数出したことが今回の引き金なので、
「1件ずつ出す」と書いた以上、そのとおりに動くこと。
