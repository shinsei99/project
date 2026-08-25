---
title: "launchd から起動すると CloudStorage が読めない。FDA を与える相手が違っていた"
emoji: "🔐"
type: "tech"
topics: ["macos", "launchd", "python", "dropbox", "claudecode"]
published: false
---

紙の書類をスマホで撮ってクラウド同期フォルダへ送り、Mac側のアプリがそれを取り込む、という運用をしています。

このアプリを **launchd で常時起動にしたら、取り込みだけが動かなくなりました**。

```
PermissionError: [Errno 1] Operation not permitted:
  '/Users/apple/Library/CloudStorage/Dropbox-個人/書類取込'
```

同じコード、同じユーザー、同じフォルダです。**ターミナルから起動すれば読めます。**

## まず疑ったところ（と、外れたところ）

`~/Library/CloudStorage/…` は macOS の保護領域（TCC の管理下）です。
なので「フルディスクアクセス（FDA）を与えればよい」と考えました。

**実行しているPython本体を FDA に追加しました。効きません。**

`/usr/bin/python3` の実体、`Python.app`、Xcode の framework 側の python、
思いつく限り追加しましたが、状況は変わりませんでした。

## 判定される相手は「責任プロセス」

TCC が見るのは、実際にファイルを開いたプロセスとは限りません。
**起動をたどった先のプロセス（responsible process）**に紐づいて判定されます。

launchd の plist は、こうなっていました。

```xml
<key>ProgramArguments</key>
<array>
  <string>/bin/bash</string>          <!-- ← ここが責任プロセス -->
  <string>/Users/apple/shorui-cabinet/run.sh</string>
</array>
```

`run.sh` を起動するのは `/bin/bash` です。そこから起動された Python は、
**bash の権限で判定されます**。だから Python 側に与えても効かなかった。

ターミナルから起動したときに読めたのも、同じ理屈です。
`Terminal.app` は FDA を持っているので、その子プロセスは通ります。

**「シェルからは読めるのに、launchd だと読めない」＝この問題**、という切り分けができます。

## 解決

**`/bin/bash` にフルディスクアクセスを与える**と、常時起動でも読めるようになりました
（システム設定 → プライバシーとセキュリティ → フルディスクアクセス。GUIで1回だけ）。

ただしこれは、**bash 全体に権限を与える**ということです。
共用マシンでは避けるべきで、うちのように用途が決まっている専用Macだから許容しています。

避けたい場合の選択肢は、こうなります。

- plist から**直接バイナリを起動**する（`ProgramArguments[0]` を python にして、そこへ FDA を与える）
- 保護領域の外へ**同期先を変える**（`~/Dropbox` などの旧来のパスに置く）
- 取り込みだけ**別のプロセス**（ユーザーの手で起動する常駐）に分ける

## 権限が無いときに、全部を止めない

もう一つ直したのは、**失敗の波及**です。

取り込みフォルダを読めないだけで、アプリの画面全体がエラーで止まっていました。
書類の検索も、手入力の登録も、保管場所の確認も、権限とは無関係なのに使えない。

いまは取り込みの部分だけ `OSError` を受け止めて、案内を出しています。

```python
try:
    entries = os.listdir(INBOX)
except OSError:
    st.info("取込フォルダを読み取れません（フルディスクアクセスの設定が必要です）。"
            "検索・手入力での登録は、このまま使えます。")
    entries = []
```

**権限が要るのは一部の機能だけ**なので、そこだけ落とす。当たり前ですが、
`try` の範囲を広く取っていると、簡単にアプリ全体が巻き込まれます。

## 動作中に権限を失うこともある

別のアプリ（駐車場の配置図ビューア）では、**動いている途中で読めなくなる**ことがありました。
起動時は読めていたのに、しばらくすると権限エラーが続く状態に入ります。

こちらは、自分で終了して起動し直させる形にしました。

```python
def _handle_permission_error(e):
    global _perm_fail_count
    _perm_fail_count += 1
    if _perm_fail_count < MAX_PERM_FAILS:
        return
    if _should_self_restart():
        os._exit(1)      # KeepAlive=true で launchd が起動し直す
    else:
        print("再起動回数の上限に達したため見合わせます（要手動確認）", flush=True)
```

大事なのは**上限**です。うちは「30分で5回まで」。
これが無いと、権限が戻らないときに再起動を延々と繰り返します。
再起動ループは、ログを埋め尽くすうえに、原因を隠します。

## まとめ

- `~/Library/CloudStorage/…` は保護領域。**launchd 由来のプロセスからは既定で読めない**
- FDA を与える相手は、実行しているプログラムではなく**起動をたどった先のプロセス**
- 切り分けは「**ターミナルからは読めるか**」
- 権限が要る機能は**局所的に落とす**。アプリ全体を巻き込まない
- 自己修復させるなら、**回数の上限**を必ず付ける
