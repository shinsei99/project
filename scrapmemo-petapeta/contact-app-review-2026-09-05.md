# App Review への連絡文（2026-09-05 に送る）

入口: https://developer.apple.com/contact/app-store （サインインが要る）

**「I would like to」の選択肢に、状況照会（status）があるかを先に確かめる。**
2026-09-04 時点でスマホで見えたのは次の7つ（下にまだあるかもしれないので**一番下までスクロールする**）:

- appeal an app rejection or app removal ← **KeyTag のアピール用（1リジェクトにつき1回きり）**
- re-instate a terminated developer program
- request an expedited app review ← **選ばない**（年1〜2回の枠。混雑期は動かなかった報告多数）
- ask a technical question about my app
- ask about using App Store Connect
- suggest a guideline change
- report an app

**状況照会の項目が無い場合**は、スクラップメモの分は **Resolution Center の既存スレッドに
同じ文面を返信する**（新しい提出にならない・同じ案件の中に記録が残る）。

---

## ① スクラップメモ 1.0.5 の状況照会（**まずこれだけ送る**）

**そのまま貼る（英語）**

```
App: スクラップメモpetapeta (Apple ID: 6793374853)
Version: 1.0.5 (build 9)
Submitted: August 29, 2026
Current status: Waiting for Review

Hello,

I would like to ask about the status of this submission. It has been in
"Waiting for Review" for seven days without any change.

This version was resubmitted on August 29 with a reply in Resolution Center,
following a Guideline 4.3(a) rejection on the same day. I have not received
any message since then.

I am not requesting an expedited review. I would only like to know whether
the submission is progressing normally, or whether anything further is needed
from me. If additional information or materials would help the review, I am
glad to provide them.

Thank you for your time.
```

**日本語（内容確認用・送るのは上の英語）**

> アプリ: スクラップメモpetapeta（Apple ID: 6793374853）／バージョン 1.0.5（build 9）／
> 提出日: 2026年8月29日／現在の状態: Waiting for Review
>
> この提出の状況を伺いたくご連絡します。7日間「Waiting for Review」のまま変化がありません。
> 8月29日の Guideline 4.3(a) によるリジェクトを受け、同日に Resolution Center へ返信を添えて
> 再提出したものです。その後、こちらには何のメッセージも届いていません。
>
> 審査を早めてほしいという依頼ではありません。通常どおり進んでいるのか、こちらから追加で
> 必要なものがあるのかを知りたいだけです。追加の情報や資料が役に立つのであれば喜んで提出します。

**書き方の決まり（事例から）**: 急かさない／議論しない／Expedited を頼まない／
4.3(a) の是非をここで蒸し返さない（それは Resolution Center の話）。

---

## ② KeyTag のアピール（**①の結果が出るまで送らない**）

**1つのリジェクトにつき1回きりの弾**。スクラップメモが動いてから、この文面を見直して送る。
選ぶ項目は `appeal an app rejection or app removal`。

**そのまま貼る（英語）**

```
App: KeyTag鍵管理 (Apple ID: 6802493580)
Version: 1.0 (build 4)
Rejection: Guideline 4.3(a) - Design - Spam, August 29, 2026

Hello,

I would like to appeal this rejection, and to first acknowledge the part that
was my fault.

Over the past two months I submitted too many apps in too short a time, and
several of them shared the same cross-platform shell, which made my
submissions look like repackaged copies of one another. I understand why that
pattern was flagged. I have stopped it: I now submit one app at a time, and I
do not reuse store text between apps.

On this app specifically, I would like to explain what it is, because it is
not a template app:

- It is an internal tool for a property management company. Staff tap an NFC
  tag attached to a physical key or a piece of equipment, and the app records
  who took it, when, and when it came back.
- It talks to our own server, which holds our own key and equipment ledger.
  The data and the workflow are specific to our business; there is no generic
  content in it.
- Its audience is our staff and the property owners we work with, not the
  general public.

Supporting material is already public, including a video that shows the NFC
tag being read on a physical key:
https://shinsei99.github.io/project/keytagnfc-support/

If a test account, a longer demo video, or revised metadata would help, please
tell me what would be most useful and I will provide it.

Thank you for reconsidering.
```

**日本語（内容確認用）**

> ・**非を先に認める**: 2か月で出しすぎた／同じ土台（Capacitor）で作ったため互いの
>   焼き直しに見えた／**もう1件ずつしか出さない・掲載文を使い回さない**
> ・**このアプリが何か**: 不動産管理会社の社内道具。鍵や備品に貼ったNFCタグを読んで、
>   誰がいつ持ち出し・いつ返したかを記録する。**自社サーバーの自社台帳**とやり取りする。
>   対象は社員とオーナーで、一般向けではない
> ・**証拠**: 実機で鍵のタグを読む動画をサポートページに公開済み
> ・**こちらから聞く**: テストアカウント・長めのデモ動画・掲載文の書き直し、どれが要るか

---

## 送ったあとの目安

| 経過 | すること |
|---|---|
| 送信後 1〜5営業日 | 返答の目安（2026年の実績） |
| 送信後 2〜3日 | 動くことが多い |
| 提出から14日（9/12）で動かない | コールバック依頼 |

## 状態のちがい（2026-09-04 API実測）

- スクラップメモ 1.0.5 … `WAITING_FOR_REVIEW` ＝**列に入っている**（沈黙は正常・長さが異常）
- KeyTag 1.0 … `REJECTED` ＝**列に入っていない**（返信だけでは審査に戻っていない）

---

## ①-b 「ask about using App Store Connect」から出す版（2026-09-04 採用）

**経緯**: Resolution Center には 8/29 に返信済みだが**6日たっても返事が無い**ため、
**別窓口から出す**ことにした（オーナー判断）。この7つの中で、**アピールの1回きりの弾を
使わずに別の担当へ届く**のはこの項目だけ。`appeal an app rejection or app removal` は
KeyTag のために温存する。

カテゴリが完全には合わないので、**冒頭で「何の件か」「なぜこの窓口か」を明示**し、
末尾に**「別の部署のものなら正しい窓口を教えてほしい」**を入れる（放置されないため／
次にどこへ出すかが確定するため）。

```
App: スクラップメモpetapeta (Apple ID: 6793374853)
Version: 1.0.5 (build 9) — submitted August 29, 2026
Current status: Waiting for Review (7 days)

Hello,

I am writing about a submission that has not moved, and about a Resolution
Center thread that has received no reply. I am using this form because that
thread has been silent for seven days.

On August 29 this version was rejected under Guideline 4.3(a). The same day I
replied in Resolution Center and resubmitted. Since then there has been no
message of any kind, and the status has stayed at "Waiting for Review".

I am not requesting an expedited review. I would like to know one of two
things: whether the submission is progressing normally, or whether something
is required from me that I have missed. If additional information, a test
account, or a demo video would help, I will provide it immediately.

If this inquiry belongs to a different team, I would be grateful if you could
point me to the correct channel.

Thank you for your time.
```

**日本語（内容確認用）**: 動かない提出と、返事の無い Resolution Center の件で連絡している／
6日沈黙しているのでこの窓口から出している／8/29に4.3(a)でリジェクト、同日返信して再提出、
以後一切の連絡が無く Waiting for Review のまま／**優先審査の依頼ではない**／
通常どおり進んでいるのか、こちらに要るものがあるのかを知りたい／テストアカウント・
デモ動画などが要るならすぐ出す／**別の部署の管轄なら正しい窓口を教えてほしい**
