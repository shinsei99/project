---
title: "ファイル名は識別子ではない — 同名スキップで写真が黙って消えていた"
emoji: "🗂"
type: "tech"
topics: ["python", "sqlite", "運用", "claudecode"]
published: true
---

業務チャットへ投稿された巡回写真を、物件ごとの共有フォルダへ自動で振り分ける道具を書いています。

「フォルダに入っているか」を数えたところ、**記録上84枚あるうち、実際に入っていたのは9枚だけ**でした。
例外は出ていません。ログにも失敗は残っていません。

原因はいくつかありましたが、いちばん根が深かったのは次の一点です。

> **保存先の同一性を、ファイル名で判断していた。**

この前提を置くと、必ず片方が壊れます。**名前が同じで中身が違うものは消え、名前が違って中身が同じものは増えます。**

## ① 名前が同じで中身が違う → 黙って消える

保存名は `撮影日_題名.拡張子` で作っていました。題名は投稿者が書いた説明文から取ります。
同じ日に同じ題名で別々の写真が投稿されると、2枚目の保存先が1枚目と同じ名前になります。

そのときの処理がこれでした。

```python
# 直す前
for it, dst in plan:
    if os.path.exists(dst):
        continue          # 同名がある＝同じ写真の再投稿だろう、と見なして飛ばす
    shutil.copy2(src, dst)
```

`continue` に理由が付いていないので、これは**例外でもなく警告でもなく、ただの正常終了**です。
「同名なら中身も同じはず」という前提が、コードの中では skip という形で無言になっている。

## ② 名前が違って中身が同じ → 静かに増える

逆側も起きていました。同じ写真をチャットへ二度投稿すると、投稿ごとに別の識別子が振られます。
識別子が違えば別物として扱われ、名前も別になれば2枚とも保存されます。
実測で **8枚（4組）が中身の同じ重複**でした。

①と②は反対向きの症状に見えますが、**どちらも「名前で同一性を決めた」ことの結果**です。

## 直し方 — 同一性は中身、名前は表示

同一性の基準を、名前から中身のハッシュに移しました。

```python
import hashlib

def _sha(p):
    with open(p, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

# (1) 保存する前に、中身が同じものを1枚に束ねる
_seen, _dedup = {}, []
for it, dst in plan:
    h = _sha(os.path.join(IMG, it["file"]))
    if h in _seen:
        skip.append(it)          # 二度投稿。記録としては1枚あれば足りる
        continue
    _seen[h] = dst
    _dedup.append((it, dst))
plan = _dedup
```

そのうえで、名前がぶつかったときの扱いを「飛ばす」から「**中身を見てから決める**」に変えました。

```python
# (2) 同名にぶつかったら、中身を比べる。違う写真のときだけ連番を振る
_used, _fixed = set(), []
for it, dst in plan:
    src = os.path.join(IMG, it["file"])
    if dst not in _used and not os.path.exists(dst):
        _used.add(dst); _fixed.append((it, dst)); continue

    if os.path.exists(dst) and _sha(dst) == _sha(src):
        skip.append(it); continue            # 中身も同じ＝重ねない

    root, ext = os.path.splitext(dst)
    i = 2
    while True:
        cand = f"{root}-{i}{ext}"
        if cand in _used: i += 1; continue
        if os.path.exists(cand):
            if _sha(cand) == _sha(src): cand = None; break
            i += 1; continue
        break
    if cand is None: skip.append(it); continue
    _used.add(cand); _fixed.append((it, cand))
plan = _fixed
```

ポイントは `_used`（この実行で使う予定の名前）と `os.path.exists`（既に置いてある名前）の**両方**を見ていることです。
片方だけだと、同じ実行の中で作る `-2` が衝突するか、前回の実行分を上書きします。

これで役割がはっきりします。

- **同一性の判断 … 中身のハッシュ**
- **ファイル名 … 人が探すためのラベル。ぶつかったら連番を足すだけ**

## おまけ ― 型が違うと、重複排除そのものが効かない

同じ道具で、もう一つ静かな不具合が出ていました。「保存済みなら飛ばす」判定が効いておらず、同じ写真を何度でも入れてしまう状態です。

```python
done = {(r[0], r[1]) for r in con.execute(
    "SELECT room_id, file_id FROM patrol_photo_saved")}   # ← SQLite の INTEGER

...
rid, fid = j.get("room_id"), j.get("file_id")             # ← 古い付属JSONは文字列
if (rid, fid) in done:                                    # ← 永遠に一致しない
    continue
```

`("123", "456")` と `(123, 456)` は別のタプルなので、集合に対する `in` は常に偽になります。
例外は出ません。**「重複排除が動いていない」という見え方すらしない**のが厄介なところでした。

```python
# 入り口で型を1つに揃える。直せないものはその場で捨てる
try:
    rid, fid = int(j.get("room_id")), int(j.get("file_id"))
except (TypeError, ValueError):
    continue
```

外部から来た識別子は、**比較に使う前に型を正規化する**。境界で一度だけ直せば、以降の比較は全部素直になります。

## 「人が消したもの」も記録する

もう一つ運用側の話です。人がフォルダを見て「これは要らない」と外した写真が、次の実行でまた戻ってきました。
保存済みの記録しか持っておらず、ファイルと一緒に記録も消していたためです。

```sql
CREATE TABLE IF NOT EXISTS patrol_photo_skip(
  room_id INTEGER, file_id INTEGER, reason TEXT,
  at TEXT DEFAULT (datetime('now')), PRIMARY KEY(room_id, file_id));
```

```python
done  = {(r[0], r[1]) for r in con.execute("SELECT room_id,file_id FROM patrol_photo_saved")}
done |= {(r[0], r[1]) for r in con.execute("SELECT room_id,file_id FROM patrol_photo_skip")}
```

同期のようなものを書くときは、**「入れた」だけでなく「入れないと決めた」も残す**。
残さないと、人の判断が毎回上書きされます。

## 結果

- 記録84枚に対し、フォルダに入っていたのは **9枚**
- 実体の消えていた分をチャットから取り直し、**74枚を回収**（1枚は投稿者が削除済みで取得不可）
- 振り分け直して **37物件・58枚**。残りは別会社の物件（意図して除外）と、人の判断が要る2枚

## まとめ

- **ファイル名は識別子ではない。** 人が付ける表示用のラベルで、衝突も改名もする
- 同名スキップは、**エラーを出さずにデータを捨てる**書き方になりやすい
- 同一性はハッシュのような中身の値で判断し、名前は衝突したら連番を足す
- 外から来た識別子は、**入り口で型を揃える**。揃っていない比較は静かに常時偽になる
- 「入れた記録」と「入れないと決めた記録」は別物。両方持って初めて、人の判断が残る
