---
title: "openpyxl で「A4に必ず収まる」帳票を作る"
emoji: "🖨️"
type: "tech"
topics: ["python", "openpyxl", "excel", "claudecode"]
published: true
---

退去時の原状回復費用の精算書を、自動で作っています。
業者の見積を読み込んで、ガイドラインに沿って貸主と借主の負担を分け、明細にする道具です。

この書類は、**印刷して退去者に渡します**。
画面で見やすくても、**印刷して列が切れていたら使えません**。

## 横は必ず1ページ。縦は書類による

明細の行数は案件によって変わります。数行のこともあれば、20行を超えることもある。

そこで、こう決めました。

| | 横（幅） | 縦（高さ） |
|---|---|---|
| 精算書（明細あり） | **必ず1ページ** | 複数ページ可 |
| 誓約書（署名あり） | **必ず1ページ** | **必ず1ページ** |

openpyxl の設定では、こうなります。

```python
from openpyxl.worksheet.properties import PageSetupProperties

def _setup_a4_print(ws, last_row: int) -> None:
    """A4縦・1ページ幅フィット・列見出し繰り返し"""
    ws.page_setup.paperSize = 9              # A4
    ws.page_setup.orientation = "portrait"
    if ws.sheet_properties.pageSetUpPr is None:
        ws.sheet_properties.pageSetUpPr = PageSetupProperties()
    ws.sheet_properties.pageSetUpPr.fitToPage = True    # ← これが要る
    ws.page_setup.fitToWidth = 1             # 横は必ず1ページ幅
    ws.page_setup.fitToHeight = 0            # 縦は複数ページ可
```

**`fitToPage = True` を立てないと、`fitToWidth` は効きません。** ここでよく詰まります。

`fitToHeight = 0` が「縦は制限しない」の意味です。`1` にすると縦も1ページに押し込むので、
明細が多い案件で文字が極端に小さくなります。

## 2ページ目に、見出しを繰り返す

明細が2ページに渡ると、2ページ目には列の見出しがありません。
「金額」「負担区分」がどの列か分からなくなります。

```python
ws.print_title_rows = f"{COLUMN_HEADER_ROW}:{COLUMN_HEADER_ROW}"
ws.print_area = f"A1:F{last_row}"
```

`print_title_rows` は、**全ページの先頭に繰り返す行**の指定です。
`print_area` も明示しておくと、余計な空白列が印刷範囲に入りません。

## 列幅は、用紙の幅から逆算する

`fitToWidth = 1` は「はみ出したら縮小する」設定なので、
列幅を適当に広げていると、**全体が縮んで字が小さくなります**。

なので、A4縦に収まる値で決め打ちしています。

```python
# A4縦1ページ幅に収めるための列幅（文字数単位）
COLUMN_WIDTHS = {"A": 20, "B": 11, "C": 8, "D": 11, "E": 11, "F": 29}
```

合計90（文字数単位）。余白を左右 0.55 インチにして、この幅がちょうど収まります。

```python
ws.page_margins.left = 0.55
ws.page_margins.right = 0.55
```

**余白と列幅はセットで決める**もので、片方だけいじると崩れます。

## 署名をもらう書類は、必ず1枚に

誓約書（退去者に署名・押印をもらう書類）は、**2枚に割れると困ります**。

割印の扱いが増えますし、片方だけ返送されることもある。
この書類だけは、縦も1ページに固定しました。

```python
ws.page_setup.fitToWidth = 1
ws.page_setup.fitToHeight = 1        # 誓約書は必ずA4 1枚
for side in ("top", "bottom"):
    setattr(ws.page_margins, side, 0.5)      # 余白も少し詰める
```

縮小されて字が小さくなるリスクはありますが、**この書類は行数が固定**なので問題になりません。
「行数が変わる書類」と「固定の書類」で、設定を変えるという判断です。

## 実際に印刷して確かめる

最後は、**PDFに書き出して見る**か、実際に刷ります。

- 右端が切れていないか
- 2ページ目に見出しがあるか
- 縮小されすぎて読めなくなっていないか

`fitToWidth` は「収める」ので、**設定として正しくても、結果が読めないことがあります**。
収まっていることと、読めることは別でした。

## まとめ

- `fitToPage = True` を立てないと `fitToWidth` は効かない
- **横は1ページ、縦は書類の性質で決める**
- 見出しは `print_title_rows` で繰り返す
- **列幅と余白はセット**。用紙の幅から逆算する
- 最後は刷って見る
