# App Review への状況照会（スクラップメモ 1.0.5）— 2026-09-05 に送る用

**送り先**: https://developer.apple.com/contact/app-store/
（"App Store Review" → "App Review status" 系の窓口。**Resolution Center の返信ではない**）

**これは提出ではない。** 返信で約束した「1件ずつ出す」を崩さないし、提出履歴にも積まれない。

## 送るときの決まり（調べた事例から）

- **急かさない・議論しない。** 事実（アプリ名・ID・提出日）と「状況を知りたい」だけ書く
- **Expedited Review は頼まない**（年1〜2回しか通らず、混雑期は動かなかった実績がある）
- 4.3(a) の是非をここで蒸し返さない。それは Resolution Center の話
- 送ったら**返事が来るまで何もしない**（取り下げ・再提出をしない）

## 本文（英語・これをそのまま貼る）

> Subject: Status inquiry — スクラップメモpetapeta (Apple ID 6793374853), version 1.0.5
>
> Hello,
>
> I am writing to ask about the status of a submission that has been in "Waiting for Review" longer than usual.
>
> - App: スクラップメモpetapeta (Apple ID: 6793374853)
> - Version: 1.0.5 (build 9)
> - Submitted: August 29, 2026
> - Current status: Waiting for Review (7 days as of today)
>
> This version was resubmitted with a reply in Resolution Center after a Guideline 4.3(a) rejection on August 29. I have not received any message since then, and the submission has not moved.
>
> I am not asking for expedited review. I would simply like to know whether the submission is progressing normally, or whether anything further is needed from me. If additional information would help the review, I am happy to provide it.
>
> Thank you for your time.
>
> Shinsei Sumi
> SHINSEI PROPERTY MANAGEMENT.K.K.

## 日本語（オーナー確認用・送るのは英語のほう）

> 件名: 状況照会 — スクラップメモpetapeta（Apple ID 6793374853）バージョン 1.0.5
>
> いつもお世話になっております。
> 通常より長く「Waiting for Review」のままの提出について、状況を伺いたくご連絡します。
>
> ・アプリ: スクラップメモpetapeta（Apple ID: 6793374853）
> ・バージョン: 1.0.5（build 9）
> ・提出日: 2026年8月29日
> ・現在の状態: Waiting for Review（本日で7日）
>
> 8月29日の Guideline 4.3(a) によるリジェクトを受け、Resolution Center に返信を添えて再提出したものです。
> その後こちらには何のメッセージも届いておらず、状態も動いていません。
>
> 審査を早めてほしいという依頼ではありません。**通常どおり進んでいるのか、こちらから
> 追加で必要なものがあるのか**を知りたいだけです。追加の情報が役に立つのであれば喜んで提出します。

## 送ったあとの目安

| 経過 | すること |
|---|---|
| 送信後 2〜3日 | 動くことが多い（事例の報告） |
| 提出から14日（9/12）で動かない | コールバック依頼（Contact Us の電話折り返し） |
| 動いた | 結果に応じて次へ。KeyTag はそのあと |

## KeyTag（Apple ID 6802493580）は別扱い

**状態が違う。** API で見ると:

- スクラップメモ 1.0.5 … `WAITING_FOR_REVIEW` ＝**列に入っている**（沈黙は正常。長さだけが異常）
- KeyTag 1.0 … `REJECTED` ＝**列に入っていない**（8/29 07:32 に Resolution Center へ返信したが、
  6日たっても状態が変わらない＝**返信だけでは審査に戻っていない**）

KeyTag を動かす手は2つ。**どちらもスクラップメモが片付いてから**（「1件ずつ出す」と書いたため）。

1. **App Review Board へのアピール**（Contact Us の別窓口）。返答の目安は5〜7営業日。
   **1つのリジェクトにつき1回だけ**なので、出すなら中身を固めてから
2. **build 5 を作って再提出**（＝リジェクト後の再提出なので、通常は24〜72時間で再審査される）
