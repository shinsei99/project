---
title: "python-docx / openpyxl で「配れる書類」にするまでに潰した4つ"
emoji: "📄"
type: "tech"
topics: ["python", "pythondocx", "openpyxl", "word", "claudecode"]
published: true
published_at: 2026-09-10 22:30
---

AIエージェントが毎日18:30に業務日報を作ります。出力は Word と Excel で、そのまま人に配ります。

**中身が正しくても、見た目が崩れていると配れません。** ここで4つ潰したので、まとめておきます。

## ① 表の罫線が、環境によって出ない

`python-docx` で表を作るとき、最初はスタイル名で指定していました。

```python
table = doc.add_table(rows=1, cols=3)
table.style = "Table Grid"      # ← これに任せていた
```

Word で開くと罫線が出ます。ところが、**別のビューアで開くと出ない**。
`Table Grid` は「そのスタイルが定義されていれば」効くものなので、解釈が環境依存になります。

罫線を自分で書き込む形にしました。

```python
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

def _table_borders(table, sz=4, color="000000"):
    """w:tblBorders を直接書く。スタイル名に頼らない"""
    tbl = table._tbl
    pr = tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{edge}")
        el.set(qn("w:val"), "single")
        el.set(qn("w:sz"), str(sz))
        el.set(qn("w:color"), color)
        borders.append(el)
    pr.append(borders)

_table_borders(table)
table.autofit = False        # 幅が人によって変わるのを止める
```

`autofit = False` も一緒に必要でした。自動調整に任せると、**開く人によって列幅が変わります**。

## ② 内部APIを触ったら、題字が消えた

Excel 側で、列幅の単位を揃えたくなりました。
openpyxl の列幅は「標準フォントの文字数」基準なので、フォントを揃えれば計算が楽になる、と考えたわけです。

```python
# やってはいけなかった
wb._named_styles["Normal"].font = Font(name="Yu Gothic", size=11)
```

書き出したファイルを開くと、**「一部の内容に問題があります」と修復ダイアログが出て、
題字（"業務日報"）が消えていました**。書式が落ちています。

アンダースコアで始まる属性は、ライブラリの内部です。触ると壊れる、という当たり前の話でした。

**列幅の単位ずれは、行の高さの見積もり側で吸収する**ことにして、この細工はやめました。
（行の高さは、実機の Excel に autofit させて採寸しています。これは別記事に書きました）

## ③ ページの末尾に `□` が残る

Word の日報で、担当者ごとにページを分けています。

```python
doc.add_page_break()      # ← これ
doc.add_heading(name, level=1)
```

出来上がったファイルを見ると、**ページの末尾に `□` がぽつんと残っていました**。

`add_page_break()` は、**改ページを持った空の段落を1つ追加します**。
その段落が、直前の箇条書き段落のスタイルを引き継いでいました。
箇条書きの記号だけが、中身のない状態で残る、という見え方です。

空段落を作らない形に変えました。

```python
h = doc.add_heading(name, level=1)
h.paragraph_format.page_break_before = True     # 見出しの前で改ページ
```

## ④ 箇条書きの折り返しが、左端まで戻る

2行目以降が記号の下に潜り込んで、読みにくい状態でした。

```python
p = doc.add_paragraph(text, style="List Bullet")
pf = p.paragraph_format
pf.left_indent = Cm(1.1)
pf.first_line_indent = Cm(-0.55)     # ぶら下げ
```

左の字下げと、1行目だけ逆方向へ戻す指定（ぶら下げインデント）の組み合わせです。
これは Word の箇条書きの標準的な作り方で、明示すればどこで開いても同じになります。

## 共通して言えること

4つとも、**「そのソフトが気を利かせてくれる部分」に任せた結果**でした。

| 任せていたもの | 起きたこと |
|---|---|
| 表スタイルの解釈 | ビューアによって罫線が出ない |
| ライブラリ内部の名前付きスタイル | ファイルが修復扱いになる |
| 改ページ関数の段落追加 | 余計な空段落が残る |
| 箇条書きの字下げ | 折り返しが左端へ戻る |

書類は、**作った本人の環境で見て終わりではありません**。
配った先の Word で、iPhone のプレビューで、印刷したときに、同じに見える必要があります。

なので、**見た目に関わるところは明示する**、という方針にしています。
指定が増えてコードは長くなりますが、「その環境ではどう見えるか」を毎回試すよりは安いです。

そして最後は、**出したファイルを実際に開いて目で見る**。
ここで挙げた4つは、どれもコードを読んでいる限り気づけないものでした。
