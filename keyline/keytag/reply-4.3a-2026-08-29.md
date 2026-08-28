# KeyTag鍵管理 — Guideline 4.3(a) への返信（2026-08-29）

## ✅ 送信済み（2026-08-29 07:32 JST）

Resolution Center の「App Reviewに返信」から、下の英文を**そのまま送った**（全文が載っていること・
末尾の `Best regards` まで欠けていないことを画面で確認）。提出ID `a47e6a37-ee0d-48dc-8a35-2559cb1b976b`。

**この1通に3つ入れてある**: ①4.3(a) への回答（アカウント全体の話として） ②にゃんこアイスの
記録削除の依頼（自分では消せないため） ③「どのアプリが重複と見なされているか教えてほしい」という質問。

**次にやること**: 返事を待つ。`python3 appstore_api.py --review com.shinsei99.keytag`。
**返事が来るまで、新規提出も再提出もしない**（週明けのスクラップメモ 1.0.5 だけは別＝配信中アプリのバグ修正）。

**送り方**: App Store Connect →「App Review」→ 該当の提出 → **Resolution Center に「返信」として送る**。
**★審査ノートに書くだけでは届かない。** 8/28 の再提出は返信を付けず審査ノートだけで出し、
同じ 4.3(a) の定型文で返ってきた（`keyline/SESSION_LOG.md`）。今回は必ず返信の形で送ること。

**★にゃんこアイスの削除依頼は、この手紙に1段落だけ入れてある。**
理由（2026-08-29 実測）: にゃんこ側のスレッドは**項目を削除済みにすると返信欄が消える**。
Apple の「アプリの却下または削除」フォームは**Appleが却下・削除したケース専用**で、
「自分で消したいのに消せない」は扱えない（2つの選択肢がどちらも `your app was rejected
or removed` 前提）。**返信欄が生きている窓口はここだけ**なので、ここから伝える。

**★この文面は KeyTag だけに使う。** 同じ文章を3本に送ると「やはり同じ型で量産している」という
最初の印象を補強してしまう。ほかの2本（にゃんこアイス／スクラップメモ）は返信しないで置く。

---

## 何を狙った文面か（送る前に読む）

前回（8/28）は「このアプリは NFC を使うから他と違う」を1,153字で説明した。**それが読まれた形跡がない**:

- 3本が約6時間のあいだに、**同一の定型文**でリジェクトされた
- うち1本（スクラップメモ 1.0.5）は**配信中アプリのUI修正だけの更新**。中身では説明が付かない

つまり見られているのは**アカウント全体の出し方**。だからこの返信は、

1. **こちらから先に、外からどう見えているかを認める**（隠すと心証が悪い）
2. **すでに止めたこと**を具体的に書く（提出直前の4本を出さずに止めた）
3. **「どのアプリが重複に見えるのか教えてほしい」と具体的に聞く**（審査側が答えられる問い）
4. アプリ固有の話は**最後に3行だけ**（前回の繰り返しをしない）

**★「また作り直します」とだけ書かないこと。** 「新しいアプリをまた出す」と読まれ、
こちらの主旨（**本数を増やさない**）と正反対に伝わる。作り直す先が
**既存アプリの中**であることを必ず同じ文に書く。

---

## 送る文面（英語・そのままコピー）

> **★「削除」とは書かない。** 2026-08-29 に実測して分かったこと:
> Apple は **Rejected 状態のアプリを削除できない**仕様（`You can't remove apps that are in
> the following states: … Rejected`）。さらに**ビルドを上げていると削除後はバンドルIDを再利用できず、
> アプリ名の所有権も失う**。にゃんこアイスは未配信なので**消しても App Store の見え方は変わらない**。
> よって削除はせず、「**再提出しない・既存アプリに内容をまとめる**」と書くのが事実に合う。

```
Hello,

Thank you for the review. Rather than only re-arguing this single app, we would like to
understand and fix the underlying issue.

We are a small property management company in Japan. Our apps are built in-house by one
developer for our own daily operations, and then published. We have never purchased or
reused an app template, and we do not share code or assets between our apps other than a
standard open-source WebView wrapper (Capacitor).

We recognize how our recent activity may look from the outside:

- We submitted several small apps in a short period, including three within about six hours
  on August 27-28.
- Several of them are built with the same open-source framework, so their native binaries
  are nearly identical in size. The actual product is the content we wrote.
- Our store descriptions and support pages followed the same in-house format.

We have stopped submitting new apps. Four additional apps that were already prepared have
been withheld, and we will not submit any new app while this is unresolved. We do intend to
keep fixing bugs in the apps that are already live, so we may submit bug-fix updates for
those.

One more thing, about a different app. "にゃんこのアイス屋さん" (com.daikyo.nyankoice,
Apple ID 6784674385) was rejected at the same time. We will not resubmit it, and we would like
to remove it from our account, but we are not able to: "Remove App" is unavailable while the
app is in the Rejected state, and the version cannot be deleted either ("The last version of
an app cannot be deleted"). The App Rejection or Removal support form does not cover this
case. If you can remove that app record, or tell us how, we would appreciate it.

Our question: if the concern is our portfolio as a whole rather than this specific app,
please tell us which apps are considered duplicative. We will consolidate or remove them.

About this app specifically: KeyTag reads and writes NDEF data on physical NFC tags that
are attached to physical keys, using Core NFC. The comparable Japanese "key ledger" apps we
found on the App Store are manual-entry only and do not use NFC. A demo video of writing and
reading a real tag, and our published server API with a reference implementation, are here:

https://shinsei99.github.io/project/keytagnfc-support/
https://shinsei99.github.io/project/keytagnfc-support/api.html

If a call would be more efficient than written replies, we would be glad to arrange one.

Best regards,
Shinichi Washimi
```

## 日本語（内容確認用・送るのは上の英語）

```
ご確認ありがとうございます。このアプリ1本について反論を繰り返すよりも、根本の問題を
理解して直したいと考えています。

私たちは日本の小さな不動産管理会社です。アプリは自社の日常業務のために開発者1名が
自分たちで作り、そのうえで公開しています。アプリテンプレートの購入・流用は一度も
ありません。アプリ間でコードや素材を共有してもいません（標準的なオープンソースの
WebView ラッパー Capacitor を除く）。

外から見てどう見えるかは理解しています。

・短期間に小さなアプリを複数提出しました（8/27〜28 には約6時間で3本）
・いくつかは同じオープンソースの枠組みで作っているため、ネイティブのバイナリは
  ほぼ同じ大きさになります。実体は私たちが書いた中身のほうです
・ストアの説明文やサポートページも、社内の同じ書式に従っていました

新規アプリの提出はすでに止めました。用意済みだった4本も出さずに保留し、この件が
解決するまで新しいアプリは出しません。なお、すでに配信しているアプリの不具合修正は
続けたいので、その更新は提出することがあります。

もう1点、別のアプリについてです。「にゃんこのアイス屋さん」
（com.daikyo.nyankoice / Apple ID 6784674385）が同時に却下されました。**再提出はしません。
アカウントからも削除したいのですが、削除できません**（Rejected 状態のあいだは「Appを削除」が
使えず、バージョンの削除もできない）。「アプリの却下または削除」のサポートフォームは
この場合を扱っていないようでした。記録を削除していただけるか、方法を教えていただけると
助かります。

おうかがいしたいこと: もし懸念がこのアプリ単体ではなく、私たちのアプリ全体に
あるのでしたら、どのアプリが重複していると見なされているか教えてください。
統合するか、取り下げます。

このアプリ固有の点だけ簡潔に: KeyTag は Core NFC を使い、物理の鍵に貼った NFC タグへ
NDEF データを読み書きします。App Store で見つかった同種の日本語「鍵台帳」アプリは
いずれも手入力のみで、NFC を使いません。実機でタグに書き込み・読み取りをしている
デモ動画と、公開しているサーバー連携仕様（参照実装つき）は下記にあります。

（URL 2件）

文面のやり取りより通話のほうが早いようでしたら、喜んで調整します。
```

## にゃんこアイスの削除について（2026-08-29 に分かったこと）

**自分では消せない。** 実測した閉じた輪:

| 試したこと | 返答 |
|---|---|
| アプリを削除（画面） | 「このアプリは現在削除できません」＝ **Rejected 状態は削除不可**（Appleドキュメント） |
| 却下版 1.0 を削除（API） | `The last version of an app cannot be deleted` ／ `A version cannot be deleted if any build has been uploaded` |
| 新しい版 1.1 を作る（API） | `You cannot create a new version of the App in the current state.` |

→ **この返信の中で Apple に削除を依頼する**（上の文面に入れてある）。
「再提出→即キャンセル」で状態を変える手もあるが、**提出イベントが1つ増える**ので今はやらない。

## 送ったあとにやること

- **ほかは何も出さない。** 返事が来るまで、新規提出・再提出・アップロードをしない
- 返事の見方: `python3 appstore_api.py --review com.shinsei99.keytag`
- **もし「ポートフォリオ全体の問題」と返ってきたら**、ゲーム5本を1本に統合する案に進む
  （小さいアプリの本数を減らすのが、4.3(a) への最も直接的な答え）
- **もし個別のアプリを名指しされたら**、その本を取り下げるか統合する
