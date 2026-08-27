---
title: "本番だけ違うものが動いていた。固定パスと、launchd の Python"
emoji: "🏭"
type: "tech"
topics: ["python", "launchd", "macos", "運用", "claudecode"]
published: true
---

同じリポジトリ、同じコードなのに、**PCによって挙動が違う**。
そういう状態を2つ抱えていました。どちらもエラーが出ないので、気づくまで時間がかかりました。

## ① コマンドの場所を、固定で書いていた

登記簿PDFの解析で、AIのCLIを呼んでいます。

```python
CLAUDE_BIN = "/opt/homebrew/bin/claude"     # 直す前
```

これは Apple Silicon の Homebrew のパスです。
**Intel Mac（Homebrew は `/usr/local`）や、`~/.local/bin` に入れているPCでは存在しません。**

そして、見つからないときの挙動がこうでした。

```python
try:
    out = subprocess.run([CLAUDE_BIN, ...], ...)
    return parse(out)
except FileNotFoundError:
    return regex_fallback(text)      # ← 静かに簡易版へ
```

**正規表現による簡易的な読み取りだけで動き続けます。** 結果は返るので、動いて見える。
ただ、取れる項目が減ります。「このPCだと精度が低い気がする」という形でしか現れません。

いまはこうしています。

```python
def _find_claude() -> str:
    """`claude` の実体を探す。**固定パスにしてはいけない。**"""
    import shutil
    found = shutil.which("claude")
    if found:
        return found
    for cand in ("~/.local/bin/claude", "/opt/homebrew/bin/claude", "/usr/local/bin/claude"):
        path = os.path.expanduser(cand)
        if os.path.exists(path):
            return path
    return "claude"
```

- **まず `shutil.which()`**（PATH から探す）
- 次に**候補のパスを順に**確認する
- それでも無ければ名前だけ返して、呼び出し時に失敗させる

そして重要なのは、**フォールバックしたことを記録に残す**ことです。
「AI解析が使えないので簡易版で処理した」と出れば、精度の違いに説明が付きます。

## ② 常時起動は、別の Python で動いていた

もう1つ。常駐しているワーカーが、**システム付属の Python** で動いていました。

```xml
<key>ProgramArguments</key>
<array>
  <string>/usr/bin/python3</string>      <!-- ← 仮想環境ではない -->
  <string>/Users/apple/chatwork-ai-manager/worker.py</string>
</array>
```

手元では仮想環境を使って開発しています。そこに `requests` を入れて書いたコードは、
**本番（システムの Python）では ImportError** になります。

対処は2つありました。

**A. 常駐も仮想環境で動かす** — 正攻法ですが、再構築のたびに気を遣います。
**B. 本番で使える範囲だけで書く** — こちらを選びました。

HTTP はすべて標準ライブラリの `urllib` で書いています。

```python
import urllib.request, urllib.error   # requests は使わない
```

そして、**理由を依存の一覧に書きました**。

```txt
# HTTP は標準ライブラリ urllib を使うため requests 等は不要。
```

これが無いと、次に触る人（未来の自分を含む）は、**普通に `requests` を足します**。
制約は、書いてあってはじめて制約になります。

## 共通する形：「本番だけ違う」は見えない

2つとも、**開発している環境では正常**でした。

| | 手元 | 本番 |
|---|---|---|
| ① | CLI がある → AI解析 | CLI が無い → 簡易版に静かに切り替え |
| ② | 仮想環境 → 動く | システムPython → ImportError |

②は起動時に落ちるのでまだ気づけます。**①は動いてしまうので、いちばん厄介**でした。

対策として決めたのは、この2つです。

- **環境に依存するものは、探す**（固定で書かない）
- **代替へ落ちたら、落ちたことを言う**

このリポジトリでは、2台のMacで同じアプリを動かしています。
片方が常時起動の本番、もう片方が開発用。
**「同じコードだから同じ動き」は、成り立たない**と思ったほうが安全でした。
