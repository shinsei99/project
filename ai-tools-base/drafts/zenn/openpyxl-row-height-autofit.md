---
title: "openpyxlの行の高さを勘で決めない。Excelのautofitを実機で採寸して合わせる"
emoji: "📏"
type: "tech"
topics: ["python", "openpyxl", "excel", "applescript", "claudecode"]
published: true
---

AIエージェントが毎日18:30に作る「業務日報」を、そのまま配れる `.xlsx` で書き出しています。
そこで**セルの文字が下で切れる**／逆の場所では**下の余白が広すぎる**という状態が続いていました。

原因は、行の高さを**根拠のない式**で決めていたことです。実機の Excel に autofit させて
正解の高さを採寸し、その値に合わせたら止まりました。採寸のやり方まで含めて書きます。

## 症状

`openpyxl` で `wrap_text=True` のセルにテキストを流し込み、行の高さを文字数から見積もっていました。

```python
# 直す前
n = sum(max(1, -(-len(ln) // 37)) for ln in (lines or ["特になし"]))
ws.row_dimensions[r].height = max(18, min(400, n * 14 + 4))
```

- B列の幅は `74`。全角なら37文字ぶんなので `len(ln) // 37` で行数を数えていた
- 1行あたり `14pt`、それに余白 `4pt`

これが**2通りの壊れ方**をしました。壊れ方が逆向きなので、片方を直すともう片方が悪化します。

| 中身 | この式の見積もり | 実測に合う高さ | 見え方 |
|---|---|---|---|
| 全角40文字 | 2行 → `2*14+4 = 32pt` | `36pt` | **4pt足りず、2行目の下が切れる** |
| 半角混じり55文字（表示幅は66） | 2行 → `32pt` | `18pt`（1行で収まる） | **14pt余って下が間延びする** |

## 原因

### 1. `len()` は全角と半角を同じ1と数える

Excel の列幅の単位は**半角1文字ぶん**です。`len()` で数えると、半角英数が混ざった行は
実際の表示幅より大きく見積もられ、折り返し行数が水増しされます。

数えるべきは文字数ではなく**表示幅**です。

```python
import unicodedata

def _text_units(text: str) -> int:
    """文字の表示幅を数える（全角=2 / 半角=1）。Excelの列幅と同じ単位。"""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F", "A") else 1 for c in text)
```

`east_asian_width` が `A`（Ambiguous）のものまで2に寄せているのは、日本語環境の游ゴシックでは
全角幅で表示されるためです。`・` や `×` のような記号がここに入ります。

### 2. `14pt` に根拠が無かった

画面を見ながら決めた数字でした。10pt の游ゴシックで折り返した1行に必要な高さは、
**実測すると 18pt** です。1行につき 4pt ずつ足りないので、2行を超えると必ず切れます。

## 直し方：実機の Excel に autofit させて採寸する

推測を捨てて、Excel 自身に「正解」を出させます。macOS なら AppleScript で
`autofit` をかけてから `row height` を読むだけです。

```applescript
set f to POSIX file "/path/to/sample.xlsx"
tell application "Microsoft Excel"
  open f
  set ws to active sheet
  set out to ""
  repeat with r in {1, 4, 5, 6}
    set rr to row (r as integer) of ws
    autofit rr
    set out to out & (r as text) & "=" & (row height of rr as text) & " "
  end repeat
  close active workbook saving no
  return out
end tell
```

生成した日報を食わせた結果です（この記事のために同じ手順を踏み直した実測値）。

```
1=27.0 4=20.0 5=36.0 6=18.0
```

- 5行目 … 表示幅66＋54で**2行**に折り返すブロック → **36pt**
- 6行目 … 1行で収まるブロック → **18pt**

**1行 = 18pt** で、折り返しは**列幅と同じ 74 単位**で起きている、と読めます。
（1行目・4行目は題字や氏名でこちらが高さを固定している行なので、採寸の対象外です）

そのまま式に落とします。

```python
def _wrapped_lines(text: str, width_units: int) -> int:
    """列幅 width_units のセルに収めたときの行数。改行も数える。"""
    n = 0
    for ln in (text or "").split("\n"):
        n += max(1, -(-_text_units(ln) // max(1, width_units)))
    return n

# 直したあと
n = _wrapped_lines(text, 74)
ws.row_dimensions[r].height = max(18, min(600, n * 18))
```

実際の日報9ブロックで突き合わせると、**8つが実測と一致**しました。残る1つはこちらが
1行多く見積もる側にずれます。**ずれるなら余白が空く側に倒す**（切れる側には倒さない）
という方針なので、これは直していません。

## ついでに踏んだ罠：標準スタイルのフォントを書き換えると、ファイルが修復扱いになる

列幅の単位を揃えたくて、`openpyxl` の内部を触ってブック既定のフォントを変えていました。

```python
wb._named_styles["Normal"].font = Font(name="游ゴシック", size=10)  # やってはいけない
```

これをやると Excel が**ファイルを破損とみなして修復扱いで開き**、その過程で
題字などの書式が落ちます。しかも「壊れています」とは出ないまま、
ただ**書式が消えた状態**で開くので気づきにくい。

アンダースコア付きの属性は公開APIではないので、素直にやめました。
単位のずれは、行の高さを多めに見積もることで吸収しています。

## 「指定しなければExcelが自動調整してくれる」は当てにしない

高さを指定しなければ Excel が勝手に整えてくれる場面はあります。ただしそれは
**開いた側のアプリと環境に依存**します。生成したファイルをそのまま人に配る用途だと、
相手の環境では効かずに潰れて見えることがありました。

**生成する側で高さを明示し、書き出したあとに読み直して確認する**のが確実です。
検証も openpyxl だけで完結します。

```python
from openpyxl import load_workbook
ws = load_workbook(path).active
print([(r, d.height) for r, d in ws.row_dimensions.items()])
# [(1, 28.0), (4, 22.0), (5, 36.0), (6, 18.0)]
```

## まとめ

- 表示幅は `len()` ではなく **全角=2・半角=1** で数える（Excelの列幅と同じ単位）
- 10pt 游ゴシックの折り返し1行は **18pt**。この値は勘で決めず、**実機に autofit させて採寸する**
- 見積もりがずれるなら、**余白が空く側**に倒す
- `openpyxl` の `_named_styles` など内部APIを触らない。修復扱いで書式が黙って落ちる

---

このツールを含む制作記録をまとめています。
👉 [制作記録：Excelの行の高さを、当てずっぽうで決めるのをやめた話](https://ai-tools-base.vercel.app/works/excel-row-height)
