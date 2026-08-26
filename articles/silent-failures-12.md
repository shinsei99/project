---
title: "人間向けの紙を、機械に読ませる。社内ツールで踏んだ不具合12本まとめ（後編）"
emoji: "📎"
type: "tech"
topics: ["python", "運用", "設計", "claudecode"]
published: true
published_at: 2026-09-19 22:30
---

[前編](https://zenn.dev/shinsei99/articles/silent-failures-10) の続きです。
不動産会社で社内ツールを30本ほど作って運用した記録から、残りの12本を索引にしました。

前編が「落ちないから気づけない」だったのに対して、こちらは
**人が読むためにできているものを、機械に渡したときに落ちるもの**が中心です。

## 11. 「指定しなければ localhost」ではない

自分専用のつもりのアプリ2本が、**社内の誰からでも開ける状態**になっていました。
Streamlit も Next.js の dev サーバーも、**既定は `0.0.0.0`** です。

https://zenn.dev/shinsei99/articles/default-bind-0000

## 12. 出力に前の案件が残る

作った書類に、**身に覚えのない会社名**が載っていました。同梱していた雛形が白紙ではなく、
他社の実案件が記入されたファイルだったためです。読み取りの代替処理が罫線を値にしていた件も。

https://zenn.dev/shinsei99/articles/leftover-in-output

## 13. 見た目が同じで、機械には別物

住所が分割できない、FAX番号が検索に当たらない、フォルダ名が一致しない。
**ハイフンに見える記号は7種類**あり、濁点は2通りの持ち方があります。

https://zenn.dev/shinsei99/articles/normalize-japanese-data

## 14. 終了コード0で中断していた

200本あるはずの書式が126本になっていました。例外で止まったのに、**終了コードは0**。
「成功した」の判定を、**成果物の件数**に変えた話です。

https://zenn.dev/shinsei99/articles/exit-code-zero-partial

## 15. 配れる書類にするまで

表の罫線が環境によって出ない、内部APIを触って題字が消える、ページ末尾に記号が残る。
**気を利かせてくれる部分に任せた結果**でした。

https://zenn.dev/shinsei99/articles/office-report-layout

## 16. キーは有効。通信も成功。それでも結果が空

似た識別子の**別のデータを呼んでいた**という話です。空の結果は正常な応答として返るので、
取り違えと「本当にデータが無い」の区別がつきません。

https://zenn.dev/shinsei99/articles/api-wrong-endpoint

## 17. 共有フォルダを固定パスで読むと、いつか古いデータを読む

空きと表示された駐車場に、先月から車が停まっていました。
**ファイル名の頭に「★要更新★」が付いた**ためで、古いコピーを読み続けていました。

https://zenn.dev/shinsei99/articles/stale-data-star-filename

## 18. AIが書いたものに、内部の記号が混じる

生成したファイル31本の末尾に、指示用のタグが残っていました。
**読ませた記号は、書かれると思ったほうがいい**という話です。

https://zenn.dev/shinsei99/articles/generated-text-leaks

## 19. 同じ秒に2件入ると、順序が決まらない

鍵の貸出台帳で、表示のたびに前後が入れ替わりました。
**時刻の精度を上げても解決しません**。`executescript()` の暗黙COMMITの件も一緒に。

https://zenn.dev/shinsei99/articles/sqlite-transaction

## 20. 読めなかったときに何を返すか

休業日の判定が効かず、**休みの日に催促が飛んでいました**。
判断材料が無いときは、**取り返しがつく側**へ倒す、という話です。

https://zenn.dev/shinsei99/articles/safe-default-on-unreadable

## 21. 本番だけ違うものが動いていた

コマンドの場所を固定で書いていたため、**あるPCでだけAI解析が静かに無効**になっていました。
常駐が別のPythonで動いていた件も。

https://zenn.dev/shinsei99/articles/env-differs-in-production

## 22. 自動では回避しないと決めた線

5本選んでも1本しか保存されない。ブラウザの制限でした。**回避できるが、しない**と決めた話です。

https://zenn.dev/shinsei99/articles/chrome-download-limit

---

## 22本を書いて

社内ツールは、**使う人が目の前にいます**。壊れたら、その日のうちに言われます。
言われない壊れ方——**動いているが古い、半分だけ動く、静かに精度が落ちる**——が、いちばん高くつきました。

書いていて気づいたのは、対処がどれも同じ形だったことです。

- **数える**（件数・残量・一致率）
- **落ちたら言う**（黙って代替へ落ちない）
- **いつの情報かを出す**
- **取り返しがつく側に倒す**

制作の記録（プロンプト・過程・改善）はこちらです。
https://ai-tools-base.vercel.app/works
