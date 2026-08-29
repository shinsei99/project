---
title: "「件数が足りているか」で分岐してはいけない。フォールバックが常に top_k を埋めていた"
emoji: "📚"
type: "tech"
topics: ["python", "sqlite", "fts5", "rag", "claudecode"]
published: false
---

社内資料を横断して答えるAIエージェントに、法令・ガイドライン・判例・実務書の索引を足しました。
既存の社内書類は 4,291 文書。ここに 262 文書・約 33,000 チャンクを追加し、
索引は合計 65,349 チャンクになりました。

設計はこうです。

1. まず社内書類だけで引く
2. **社内書類では答えが薄いときだけ**、法令・判例・書籍まで広げる

「最初から全部見る」と、業務の質問に一般論が混ざります。
「合図の語でだけ広げる」と、言い回しが違うだけで届きません。だから二段構えにしました。

ところが、**この「広げる」が一度も動きませんでした。**
索引には確かに入っているのに、答えの根拠はいつも社内書類だけでした。

## 検索は二段構えだった

検索は SQLite の FTS5（trigram）が主で、当たらなければ LIKE で補う形です。

```sql
CREATE VIRTUAL TABLE knowledge_fts USING fts5(
    text,
    ...
    tokenize='trigram'
);
```

```python
TOP_K = 12

def _search_once(question, top_k, kinds):
    terms = _terms(question)
    results = {}

    # 1) FTS5 (trigram)
    fts_terms = [t for t in terms if len(t) >= 3]   # trigram なので3文字未満は渡せない
    if fts_terms:
        match_expr = " OR ".join(f'"{t}"' for t in fts_terms)
        for r in query("... WHERE knowledge_fts MATCH ? ... ORDER BY score LIMIT ?", ...):
            results[r["id"]] = dict(r)

    # 2) 本文 LIKE で補う
    if len(results) < top_k:
        for t in terms:
            for r in query("... WHERE c.text LIKE ? ... LIMIT ?", (f"%{t}%", ..., top_k)):
                results.setdefault(r["id"], dict(r))

    # 3) 文書名・ファイル名 LIKE でも補う（「○○のマニュアルどこ？」対応）
    ...
    return list(results.values())[:top_k]
```

そして「広げるかどうか」の判定を、こう書いていました。

```python
rows = _search_once(question, top_k, [KIND_OWN])

if widen and len(rows) < WIDEN_MIN:          # ← これが動かない
    rows = _search_once(question, top_k, [KIND_OWN, KIND_LAW, KIND_CASE, KIND_BOOK])
```

## 原因：件数は、いつも上限に届いていた

各行に「どちらで拾ったか」の印を付けて数えてみました。

```python
for r in rows:
    r["_via"] = "fts"   # または "like"
```

実測です。

```
Q=「敷金の返還はどこまで認められますか」
  検索語 ['返還', '敷金']         件数=12  fts=0   like=12

Q=「原状回復のガイドラインでは通常損耗はどう扱いますか」
  検索語 ['ガイドライン', '原状回復', '通常損耗']  件数=12  fts=12  like=0

Q=「定期借家契約の再契約で注意する点は」
  検索語 ['定期借家契約', '再契約', '注意']       件数=12  fts=12  like=0
```

1つめの質問は、**FTS5 に1語も渡っていません。**
検索語が `返還` `敷金` の2文字語だけで、trigram の索引には 3 文字未満を渡せないからです。
FTS が丸ごとスキップされ、LIKE の `%敷金%` が 12 件を埋めます。

LIKE の一致は弱くていい加減です。「全ファイル一覧」のような、
その語が1回出てくるだけのチャンクでも枠に入ります。
それでも `len(rows)` は 12 です。上限に届いています。

つまり **`len(rows) < WIDEN_MIN` は原理的に成立しません。**
フォールバックが存在する検索で件数を見るのは、「補いが仕事をしたか」を見ているだけで、
「主の検索が当たったか」を見ていない。ここが間違いでした。

## 直し方：件数ではなく「強く当たった数」で分岐する

```python
WIDEN_MIN = 3

rows = _search_once(question, top_k, kinds)

# ★件数ではなく「FTSで強く当たった数」で判定する。
#   LIKE のフォールバックは弱い一致でも top_k を埋めるので、
#   件数で見ると*いつも足りている*ことになり、永久に広がらない。
strong = sum(1 for r in rows if r.get("_via") == "fts")

if widen and strong < WIDEN_MIN and set(kinds) <= {KIND_OWN}:
    rows = _search_once(question, top_k, [KIND_OWN, KIND_LAW, KIND_CASE, KIND_BOOK])
```

先ほどの `敷金` の質問は `strong == 0` なので、確実に広がります。
逆に社内書類に本物のヒットが 3 件以上ある質問（進捗確認など）は広がらず、
一般論が混ざりません。

**フォールバックを足した瞬間に、「件数」は品質の指標ではなくなります。**
段を足したなら、段ごとに数を持つ。これが教訓でした。

## ついでに踏んだ：混ぜると量の多い棚が上位を独占する

判定を直したら、次はこれが出ました。
複数の棚を対象にしても、まとめて1回で引くと**社内書類が上位を全部埋めます**。
社内書類は 4,291 文書、法令は 21 文書。件数が違いすぎます。

種別ごとに引いてから混ぜる形にしました。

```python
if len(kinds) > 1:
    rows, seen = [], set()
    extra = [k for k in kinds if k != KIND_OWN]
    share = max(2, top_k // (len(extra) + 2))   # 自社に厚め、他は最低2件
    for k in extra:
        for r in _search_once(question, share, [k]):
            if r["id"] not in seen:
                seen.add(r["id"]); rows.append(r)
    for r in _search_once(question, top_k - len(rows), [KIND_OWN]):
        if r["id"] not in seen:
            seen.add(r["id"]); rows.append(r)
    return rows[:top_k]
```

修正後の実測です（`source_kind` ごとの内訳）。

```
「敷金の返還はどこまで認められますか」      → 自社6 / 法令3 / 判例3
「解約から原状回復までの手順を教えて」      → 自社8 / 法令4
「来月の家賃入金の確認はどうなってる」      → 自社12
```

3つめのように業務の進捗を聞く質問では、棚は広がりません。狙いどおりです。

## もうひとつの設計判断：合図は「切り替え」ではなく「追加」

質問の言い回しから棚を決める部分は、**必ず社内書類を含めたまま足す**形にしました。

```python
def kinds_from_question(question):
    """質問の言い回しから、見に行く資料の種別を決める。自社書類は必ず含む。"""
    kinds = [KIND_OWN]
    ...
```

切り替え式にすると、「トラブル」のような一語で社内の資料が答えから消えます。
業務で使うシステムでは、これは実害です。

追加にしておけば、**合図が誤爆しても社内書類は残る**ので、
反応する語を大胆に増やせます。判定の安全側がどちらかを先に決めておくと、
その後のチューニングが怖くなくなります。

## まとめ

- 検索にフォールバックを足したら、**件数は品質の指標として死ぬ**。段ごとに数を持つ
- trigram の全文検索は 3 文字未満を索引できない。**2文字語だけの質問は主検索が丸ごとスキップされる**
- 母数の違う索引を混ぜるときは、**種別ごとに枠を確保**しないと多いほうが独占する
- 分野の合図は「切り替え」ではなく「追加」にする。誤爆しても元の資料が残る

「動かない」ではなく「一度も動かない」ときは、条件式そのものが成立し得ない形になっていないかを疑うのが早いです。
