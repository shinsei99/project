---
title: "「そのフォルダは存在しません」は嘘だった。クラウドのIDは1つとは限らない"
emoji: "🔗"
type: "tech"
topics: ["python", "sqlite", "macos", "googledrive", "claudecode"]
published: true
---

社内資料に答えるAIエージェントを運用しています。物件の資料はクラウドの共有フォルダに置いてあり、
チャットには「この物件です」と**フォルダのURLがそのまま貼られます**。

貼られたURLをAIが取りに行っても、非公開なので認証で弾かれます。
なので、URLを**同期済みのローカルの実体に読み替える**道具を作りました。

その道具が、**実在するフォルダを「存在しません」と答えました。**
しかも「同期されていない別フォルダでは」「ゴミ箱にある古いものでは」という、
もっともらしい説明まで添えて。私も裏を取らずに「約4万件を探しましたが見つかりません」と報告しました。

そのフォルダは、同期済みで手元にありました。

## 最初の実装：フォルダに付いた識別子を突き合わせる

デスクトップ同期アプリは、同期したフォルダの**拡張属性**にクラウド側の識別子を書き込みます。
URLに含まれる識別子と一致するものを探せば場所が分かる、という発想でした。

```python
# 最初の実装（いまは残していない）
import subprocess, os

ATTR = "com.google.drivefs.item-id"

def find_by_xattr(root, want_id):
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            p = os.path.join(dirpath, d)
            r = subprocess.run(["xattr", "-p", ATTR, p], capture_output=True)
            if r.stdout.decode("utf-8", "replace").strip() == want_id:
                return p
    return None   # ← ここに落ちて「存在しません」になった
```

これは**2つの理由で失敗**しました。

### 理由1：遅い。9分かけても終わらない

`os.getxattr` は **Linux 専用**で、macOS の Python には生えていません。

```python
>>> import os, sys
>>> sys.platform, hasattr(os, "getxattr")
('darwin', False)
```

`xattr` モジュールも標準では入っていないので、外部コマンドを1ファイルにつき1回起動していました。
このプロセス起動が効きます。手元で測ると：

```python
import subprocess, time
t = time.time()
for _ in range(200):
    subprocess.run(["xattr", "-p", "com.apple.lastuseddate#PS", "/Users/apple"],
                   capture_output=True)
print(round((time.time() - t) / 200 * 1000, 2))   # → 2.59 (ms)
```

**1回あたり 2.59ms。** 対象が約4万件なので、**プロセス起動だけで約1.8分**。
これにクラウド同期のファイルシステム越しの `stat` と `walk` が乗り、実際には**9分かけても終わりません**でした。

ここは `xattr -p <属性> <file1> <file2> ...` が複数ファイルを一度に受けるので、
数百件ずつまとめれば桁で速くなります。**が、それでは理由2が直りません。**

### 理由2：同じフォルダが、複数の識別子を持っていた

URLの識別子と、拡張属性から読める識別子が、**同じフォルダなのに違っていました**。

クラウド側は、作り直しや移動の履歴で**古い識別子と新しい識別子を両方生かしておくこと**があります。
一方、拡張属性から読めるのは**そのうち1つだけ**。
だから、人が古いほうのURLをコピーして貼ると、突き合わせは永遠に一致しません。

そして、一致しなかったときにこの実装が返せる答えは「見つかりません」だけです。
**探し方が不完全なのに、結論は「存在しない」という断定になる。** ここが今回の本題です。

## 直した実装：同期アプリのローカル索引を引く

デスクトップ同期アプリは、ローカルに **SQLite の索引**を持っています。

```
~/Library/Application Support/Google/DriveFS/<数字>/metadata_sqlite_db
  items          … stable_id / id(クラウド側の識別子) / local_title / is_folder / trashed
  stable_parents … 親子関係（item_stable_id → parent_stable_id）
```

この索引は、同期アプリが知っている識別子を**全部**持っています。だから取りこぼしません。
しかも `items.id` には一意索引が付いているので、走査そのものが要りません。

```python
>>> con.execute("explain query plan select stable_id from items where id=?", ("x",)).fetchall()
[(2, 0, 39, 'SEARCH items USING COVERING INDEX sqlite_autoindex_items_1 (id=?)')]
```

実測（同一Mac・2026-08-31）:

- `items` **54,737行** / `stable_parents` **54,720行** / DB本体 **67.7MB**
- 索引DBのコピー（`-wal` / `-shm` 込み）**0.066秒**
- 識別子での引き当て **2,000件で 0.007秒**

**9分（未完了）→ 0.45秒**になりました。

### 原本は開かない。ジャーナルごとコピーする

同期アプリは常駐していて、索引をいつでも書き換えています。
原本を直接開くのは避け、`-wal` / `-shm` ごと一時ディレクトリへコピーしてから読みます。
こうすると、**まだ本体に反映されていない書きかけの内容も含めて**読めます。

```python
def _open_db():
    hits = sorted(glob.glob(os.path.join(DRIVEFS, "*", "metadata_sqlite_db")))
    if not hits:
        return None, "索引が見つかりません"
    src = hits[-1]
    tmp = os.path.join(tempfile.mkdtemp(prefix="drivefs-"), "db")
    shutil.copy2(src, tmp)
    for ext in ("-wal", "-shm"):          # ★ ジャーナルも一緒に持っていく
        if os.path.exists(src + ext):
            shutil.copy2(src + ext, tmp + ext)
    con = sqlite3.connect(tmp)
    con.row_factory = sqlite3.Row
    return con, None
```

### 親をたどってパスを組む

索引はフルパスを持っていないので、親子関係の表を再帰でたどって組み立てます。
壊れた索引や循環で無限に潜らないよう、深さで打ち切ります。

```python
def _path_of(con, stable_id, depth=0):
    if depth > 20:
        return ""
    row = con.execute(
        "SELECT parent_stable_id FROM stable_parents WHERE item_stable_id=?",
        (stable_id,)).fetchone()
    if not row:
        return ""                      # ルートに着いた
    par = con.execute(
        "SELECT stable_id, local_title FROM items WHERE stable_id=?",
        (row["parent_stable_id"],)).fetchone()
    if not par:
        return ""
    return _path_of(con, par["stable_id"], depth + 1) + "/" + (par["local_title"] or "?")
```

あとは、組み立てたクラウド上のパスをローカルのマウント位置に接ぎ木すれば実体に届きます。

### URLから識別子を取り出す

貼られるURLは1つの形とは限りません。フォルダ・ファイル・古い形式の3つを拾います。

```python
_ID_RE = re.compile(r"/(?:folders|d)/([A-Za-z0-9_\-]{10,})|[?&]id=([A-Za-z0-9_\-]{10,})")
```

## 見つけたあと：会社の壁を通す

ここまでで「URLさえ知っていれば、置き場が分かる」道具になりました。
索引には**全社の資料**が入っているので、このまま返すと抜け道になります。

割り出したパスが、**いまの会社の資料ルートの下にあるときだけ**返すようにしました。

```python
if not any(os.path.abspath(path) == x or os.path.abspath(path).startswith(x + os.sep)
           for x in roots):
    out.append({"id": i, "found": False,
                "note": "別の会社のものなので、ここからは扱えません"})
    continue
```

このとき、**「索引に無い」と「別会社なので扱えない」を別の文言で返す**のが大事でした。
同じ「見つかりません」にまとめると、今度は人間が理由を取り違えます。

```python
out.append({"id": i, "found": False,
            "note": "索引にありません（削除済み、または別アカウント）"})
```

判定はプロンプトでお願いするのではなく、**コードの分岐で見えなくします**。見えないものは漏らせません。

## おまけ：対応拡張子を足したのに読めない

同じ日に踏んだ、毛色は違うが原因が同型のもの。

古い形式のOffice文書（`.xls` / `.doc`）を索引に載せようとして、`SUPPORTED_EXT` に足したのに
1件も増えませんでした。原因は、**拡張子から読み取り関数を引く表**に足していなかったこと。

```python
SUPPORTED_EXT = {".pdf", ".docx", ".xlsx", ".xls", ".doc"}   # ← ここだけ足した
_EXTRACTORS   = {".pdf": _pdf, ".docx": _docx, ".xlsx": _xlsx}  # ← ここが漏れていた
```

対象には入るが、読み取り関数が無いので**静かに素通り**します。エラーも出ません。
両方に足したら、取引・契約フォルダの索引が **713件 → 1,255件** になりました。

## 学んだこと

**「無い」という答えは、探し方の完全性に全面的に依存します。**

「有る」は1件見つければ証明できますが、「無い」は探索範囲の全部を見たと言えないと成立しません。
今回の実装は**フォルダあたり1つの識別子しか見ていない**のに、
一致しなかっただけで「存在しない」と断定していました。

そのうえAIは、**その断定に理由を付けます。**
「同期されていないのでは」「ゴミ箱にあるのでは」——どちらも観測していない作り話です。
返り値が `found: False` の一種類しかないので、理由の欄は埋めようがなく、埋めれば作文になります。

だから、否定を返す道具を書くときは:

- **探索の完全性を、道具の側で保証する**（全識別子を持つ索引を引く／取りこぼす方式を選ばない）
- **「無い」の種類を分けて返す**（索引に無い／権限で扱えない／同期されていない）
- 遅い実装は、ただ遅いだけでなく**「途中で諦めた結果」を「無い」と呼びがち**なので疑う

最初の実装を速くする（複数ファイルをまとめて `xattr` に渡す）方向にも進めましたが、
それでは**間違った答えが速く返ってくるだけ**でした。
