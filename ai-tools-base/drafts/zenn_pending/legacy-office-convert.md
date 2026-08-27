---
title: "古い .doc / .xls / 横向きスキャン。中身を読む前に形を揃える"
emoji: "🗂️"
type: "tech"
topics: ["python", "pythondocx", "pymupdf", "ocr", "claudecode"]
published: true
---

不動産の書類は、**古い形式のまま渡ってきます**。

- 公式書式（協会が配布）は `.doc`
- 他社の物件資料は `.xls`（画像が埋め込まれている）
- 現地で撮った書類は、横向きの PDF

中身の処理を書く前に、**形を揃える**必要がありました。ここでやったことをまとめます。

## ① `.doc` を、表を壊さずに `.docx` へ

`python-docx` は `.doc`（旧バイナリ形式）を読めません。公式書式14本がそれでした。

試して駄目だったもの:

- **Word に AppleScript で `save as` させる** → 現行の Word で `-1708`（イベントを受け付けない）
- **`antiword` / `catdoc`** → テキストは取れるが**表の構造が消える**。書式に流し込む用途では使えない
- **LibreOffice の `--convert-to`** → 動くが、常駐環境に LibreOffice を入れたくない

結局、2段構えになりました。

```bash
# 1. OS付属の textutil で RTF へ
textutil -convert rtf -output out.rtf in.doc

# 2. pandoc で docx へ
pandoc out.rtf -o out.docx
```

ここで**文字化け**が出ます。`textutil` が出す RTF は、日本語を `\'xx`（CP932のバイト）で書きます。
pandoc はこれを正しく解釈しないので、変換前に Unicode エスケープへ置き換えました。

```python
def _cp932_escapes_to_unicode(rtf: bytes) -> bytes:
    """\\'xx\\'yy の並びを CP932 として復号し、\\uNNNN? へ置き換える"""
    def repl(m):
        raw = bytes(int(h, 16) for h in m.group(0).decode().split("\\'")[1:])
        try:
            s = raw.decode("cp932")
        except UnicodeDecodeError:
            return m.group(0)
        return "".join(f"\\u{ord(c)}?" for c in s).encode()
    return re.sub(rb"(?:\\'[0-9a-fA-F]{2})+", repl, rtf)
```

**表の構造は保たれます。** これで14本を流し込みの対象にできました。

## ② `.xls` に埋め込まれた画像を、外部ツールなしで取り出す

他社のマイソク（物件資料）は `.xls` で届き、**写真がシートに貼られています**。
これを取り出したい。ファイルをバイナリ走査して JPEG のマジックナンバーを探しても、**見つかりません**。

理由は、**二段で分断されている**からです。

**1段目：OLE 複合ドキュメント**
`.xls` は OLE のコンテナで、`Workbook` ストリームが**512バイトのセクタに散っています**。

```python
import olefile
ole = olefile.OleFileIO(path)
wb = ole.openstream("Workbook").read()   # ここで連結された状態になる
```

**2段目：BIFF レコードの CONTINUE**
BIFF は 1レコード **8224バイト**が上限です。画像を含む `MSODRAWINGGROUP`(0x00EB) は
`CONTINUE`(0x003C) に刻まれています。

```python
# 0x00EB とそれに続く 0x003C を連結する
pos, buf = 0, bytearray()
while pos < len(wb):
    rec, size = struct.unpack_from("<HH", wb, pos)
    body = wb[pos+4: pos+4+size]
    if rec == 0x00EB:
        buf += body
        pos += 4 + size
        while pos < len(wb):
            rec2, size2 = struct.unpack_from("<HH", wb, pos)
            if rec2 != 0x003C:
                break
            buf += wb[pos+4: pos+4+size2]
            pos += 4 + size2
        break
    pos += 4 + size
```

連結すれば、あとは Escher の構造を素直に辿れます。

```
DggContainer(0xF000) → BStoreContainer(0xF001) → BSE(0xF007) → BLIP
```

`BSE` ヘッダは36バイト。BLIP は `recInstance` の最下位ビットが立っていると UID が2個（32バイト）、
その後ろに tag が1バイト。中身は JPEG / PNG / DIB です。
DIB は BITMAPINFOHEADER だけなので、BMP のファイルヘッダを足せば PIL で開けます。

同じ型の資料は**先頭に共通の枠画像**が入っていることがあるので、SHA-1 で除外しています。

## ③ 読ませる前に、向きを直す

スキャンした書類は、**横向きや逆さ**のことがあります。そのまま AI に渡すと、

- **遅い**
- **取りこぼす**（氏名など、回転していると読めない）

実測で **479秒 → 108秒**。取りこぼしも解消しました。

やっていることは単純です。

1. 各ページを画像化する（PyMuPDF）
2. **サムネイルを軽いモデルに渡して**、正立に必要な回転角（0/90/180/270）を判定する
3. `im.rotate(-ang, expand=True)` で回す
4. そのうえで本命のモデルに読ませる

判定に軽いモデルを使うのが要点です。**向きの判定に高い精度は要らない**ので、
ここで重いモデルを使うと、時間も費用も無駄になります。

共通部品として切り出して、PDFを読むアプリ全部に配りました。

```python
ensure_upright_pdf(pdf_bytes)          # テキストPDFは無変換、スキャンだけ正立
ensure_upright_image(image_bytes)      # 1枚画像
ensure_upright_bytes(data, filename)   # 拡張子で振り分け
```

いずれも**例外を投げず、失敗したら元のデータを返します**。
前処理が落ちて本処理が止まるのは本末転倒なので、ここは必ずそうしています。

## まとめ

- `.doc` は `textutil` → RTF →（CP932エスケープを変換）→ pandoc → `.docx`
- `.xls` の画像は **OLEセクタ**と **BIFFのCONTINUE**、二段の分断を解く
- スキャンPDFは**読む前に正立**させる。判定は軽いモデルで十分
- 前処理は**失敗しても元を返す**

古い形式は、こちらの都合ではなくなりません。相手が使い続ける限り、届き続けます。
**中身の処理より先に、形を揃える層を持っておく**と、あとが楽になります。
