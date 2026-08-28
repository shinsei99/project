# にゃんこのアイス屋さん — 削除したい旨の連絡（2026-08-29）

## ★Resolution Center には返信できない

提出物の項目を「削除済み」にした時点で、**あのスレッドには返信欄が無くなる**（2026-08-29 実測。
Apple のメッセージの下は提出日・提出ID・提出者で終わり、入力欄が出ない）。

**したがって窓口は「お問い合わせ」**:

https://developer.apple.com/contact/app-store-connect/

→ 「App Store Connect」→「Apps」系の項目（App の削除・アカウントの整理に近いもの）を選ぶ。

## 添える情報（これがあると早い）

| 項目 | 値 |
|---|---|
| App 名 | にゃんこのアイス屋さん |
| Apple ID | **6784674385** |
| バンドルID | com.daikyo.nyankoice |
| 提出ID | **df31c91f-c4d3-4be2-84ec-8f2cbbb141d5** |
| 状態 | 1.0 が Rejected（4.3(a)）。**一度も配信していない** |

## 送る文面（英語・そのままコピー）

```
Hello,

I would like to remove one of my apps from my account, but the Remove App option is not
available.

App: にゃんこのアイス屋さん
Apple ID: 6784674385
Bundle ID: com.daikyo.nyankoice
Submission ID: df31c91f-c4d3-4be2-84ec-8f2cbbb141d5

The app has never been released. Version 1.0 was rejected under Guideline 4.3(a) on
August 29, 2026, and I do not intend to resubmit it. I have already removed the item from
the review submission.

I cannot remove the app myself:
- "Remove App" reports that the app cannot be removed in its current state (Rejected).
- Deleting the version is also refused: "The last version of an app cannot be deleted" and
  "A version cannot be deleted if any build has been uploaded".

Could you remove this app record from my account, or tell me how I can do it myself?

I have also stopped submitting new apps while I review my approach.

Best regards,
Shinichi Washimi
SHINSEI PROPERTY MANAGEMENT.K.K.
```

## 日本語（内容確認用・送るのは上の英語）

```
アカウントから1本のアプリを削除したいのですが、「Appを削除」が使えません。

App: にゃんこのアイス屋さん / Apple ID: 6784674385 /
Bundle ID: com.daikyo.nyankoice / 提出ID: df31c91f-c4d3-4be2-84ec-8f2cbbb141d5

このアプリは一度も配信していません。1.0 が 2026年8月29日に Guideline 4.3(a) で
却下され、再提出するつもりはありません。審査提出からは既に項目を削除しました。

自分では削除できません:
・「Appを削除」は、現在の状態（Rejected）では削除できないと表示されます
・バージョンの削除も断られます（「最後の版は削除できない」「ビルドを上げた版は削除できない」）

この App の記録を削除していただけますか。あるいは、自分で削除する方法があれば教えてください。

なお、新規アプリの提出は、進め方を見直すあいだ止めています。
```

## 送ったあと

- 状態の確認: `python3 ../appstore_api.py --review com.daikyo.nyankoice`
- **記録が消えたら**: `CLAUDE.md` のゲーム表と `nyanko-ice/TODO.md` を「削除済み」に更新する
- **消えなくても実害はない**（未配信なので App Store には出ていない）
- **Web版（https://shinsei99.github.io/project/nyanko-ice/）はそのまま公開を続ける**

## 経緯（自分では削除できないことの実測）

| 試したこと | 返答 |
|---|---|
| アプリを削除（画面） | 「このアプリは現在削除できません」＝ Rejected 状態は削除不可（Apple ドキュメント） |
| 却下版 1.0 を削除（API） | `The last version of an app cannot be deleted` ／ `A version cannot be deleted if any build has been uploaded` |
| 新しい版 1.1 を作る（API） | `You cannot create a new version of the App in the current state.` |
| Resolution Center に返信 | **返信欄が無い**（項目を削除済みにするとスレッドが閉じる） |
