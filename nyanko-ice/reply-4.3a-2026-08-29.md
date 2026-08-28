# にゃんこのアイス屋さん — 4.3(a) への返信（2026-08-29）

**送り先**: https://appstoreconnect.apple.com/apps/6784674385/distribution
→ 左メニュー「**App Review**」→ 該当の提出（昨日 17:07）→ **Resolution Center に返信**

**趣旨**: 争わない。**このアプリは再提出しない／アカウントからも消したい**という意向だけを伝える。
自分では削除できない（下記）ので、方法があれば教えてほしいと聞く。

**★短く保つこと。** KeyTag に送る文面（`keyline/keytag/reply-4.3a-2026-08-29.md`）とは
**別の内容・別の長さ**にする。同じ文章を複数のアプリに送ると「同じ型で量産している」という
最初の指摘を補強してしまう。

**★自分では削除できない理由**（2026-08-29 実測）

| 試したこと | 返答 |
|---|---|
| アプリを削除（画面） | 「このアプリは現在削除できません」＝ Rejected 状態は削除不可（Apple ドキュメント） |
| 却下版 1.0 を削除（API） | `The last version of an app cannot be deleted` ／ `A version cannot be deleted if any build has been uploaded` |
| 新しい版 1.1 を作る（API） | `You cannot create a new version of the App in the current state.` |

---

## 送る文面（英語・そのままコピー）

```
Hello,

Thank you for the review. We are not going to contest this decision.

We will not resubmit this app. We would also like to remove it from our account entirely.
It has never been released.

We cannot do that ourselves: the Remove App option is unavailable while the app is in the
Rejected state, and the version cannot be deleted either ("The last version of an app cannot
be deleted", "A version cannot be deleted if any build has been uploaded"). If you are able
to remove this app record, please do, or please let us know how we can.

We have also stopped submitting new apps while we review our approach.

Best regards,
Shinichi Washimi
```

## 日本語（内容確認用・送るのは上の英語）

```
ご確認ありがとうございます。この判断に異議を申し立てるつもりはありません。

このアプリを再提出することはありません。あわせて、アカウントからも完全に削除したいと
考えています（一度も配信していないアプリです）。

ただ、自分たちでは削除できません。Rejected 状態のあいだは「Appを削除」が使えず、
バージョンの削除もできません（「最後の版は削除できない」「ビルドを上げた版は削除できない」）。
そちらで App の記録を削除していただけるか、方法を教えていただけると助かります。

なお、新規アプリの提出は、進め方を見直すあいだ止めています。
```

## 送ったあと

- 状態の確認: `python3 ../appstore_api.py --review com.daikyo.nyankoice`
- **記録が消えたら**: `CLAUDE.md` のゲーム表と `nyanko-ice/TODO.md` を「削除済み」に更新する
- **消えなくても実害はない**。一度も配信していないので App Store には出ていない
- **Web版（https://shinsei99.github.io/project/nyanko-ice/）はそのまま公開を続ける**
