#!/usr/bin/env python3
"""自然文の質問に、**試しながら**答える検索（2026-08-31）。

    /usr/bin/python3 ai_search.py "9月2日のスイスホテルの懇親会の詳細　1ヶ月以内のメール"

## なぜ作ったか（オーナー指摘）

> 「懇親会・スイスホテル・1ヶ月以内、の単語で検索するってAIのレベルじゃないでしょ？
>  機械的にやってるレベルじゃん。設計ミスじゃないの？」

そのとおりだった。従来の `ai_query.parse_query` は
**自然文を1回だけJSONに変換 → その条件で1回検索 → 0件ならそこで終了**で、
**結果を見て条件を変える工程が無かった**。実際に 2026-08-31 に次のことが起きた。

- 「9月2日」を**捨てた**（期間表現でもキーワードでもない語の受け皿が無い）
- 「懇親会」と「スイスホテル」を**ANDの必須語**にした（固有名詞2つのANDは0件になりやすい）
- **0件でも何もせず終了**した（緩める・言い換える・期間を外す、を試さない）

人なら「0件？ じゃあ懇談会かも」「期間を外してみよう」と必ずやり直す。それを機械にやらせる。

## 作り（大事なところ）

**LLMに全部やらせない。** claude は60秒で落ちることがあり、落ちたら検索そのものが死ぬ。
だから**緩め方の階段は決定的（Python側）**にして、LLMは次の3つだけに使う。

1. 初手の条件づくり（`ai_query.parse_query`。失敗しても質問文から語を拾って続行する）
2. 0件が続いたときの**言い換え語**の提案（静的な辞書で足りなければ聞く）
3. 最後の**答えの文**（「このメールです。会場は〜」まで書く。一覧を出して終わりにしない）

緩め方の階段（上から順に試し、ヒットしたら止める）:

| # | やること | なぜ |
|---|---|---|
| 1 | 表記ゆれを展開してAND | 「9月2日」は `９月２日` `9/2` とも書かれる |
| 2 | 期間を外す | 「1ヶ月以内」の外に本命があることは普通にある（**範囲外に何件あるかを必ず報告する**） |
| 3 | 必須語を1つずつ落とす | 固有名詞2つのANDは0件になりやすい。落とす順は**珍しい語を残す** |
| 4 | 言い換えを足してOR | 懇親会↔懇談会。本文の表記は書き手が決めるので、こちらが合わせる |
| 5 | 意味（ベクトル）検索へ | 語が1つも一致しないとき最後の手 |

**添付の中身も対象**（2026-08-31 に索引へ入れた）。本文に無い事実が添付にしか
書かれていないことがある（実例: PTA大会の会場はスキャンPDFの中にしか無かった）。
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import date
from typing import Any, Callable, Dict, List, Optional

import ai_query
import db

# 言い換えの静的辞書。**LLMを呼ばずに効く**ぶんだけ書く（呼べない/落ちたときの保険）。
# 実際に外した語から足していくこと。
SYNONYMS: Dict[str, List[str]] = {
    "懇親会": ["懇談会", "懇話会", "親睦会"],
    "懇談会": ["懇親会", "懇話会"],
    "打合せ": ["打ち合わせ", "打合わせ", "ミーティング", "会議"],
    "打ち合わせ": ["打合せ", "打合わせ", "ミーティング", "会議"],
    "説明会": ["説明会", "セミナー", "勉強会"],
    "見積": ["見積り", "見積もり", "御見積"],
    "請求書": ["ご請求", "請求"],
    "案内": ["ご案内", "お知らせ"],
}

_ZEN = "０１２３４５６７８９"
_HAN = "0123456789"


def _to_han(s: str) -> str:
    return s.translate(str.maketrans(_ZEN, _HAN))


def _to_zen(s: str) -> str:
    return s.translate(str.maketrans(_HAN, _ZEN))


def term_variants(term: str) -> List[str]:
    """1語 → 表記ゆれの集合（OR で使う）。

    ★ここが「9月2日で反応しなかった」件の対処。本文の書き方はメールごとに違う:
      `9月2日` / `９月２日` / `9/2` / `9月2日(水)`。どれか1つだけで探すと落ちる。
    """
    out = {term}
    han, zen = _to_han(term), _to_zen(term)
    out |= {han, zen}
    m = re.match(r"^(\d{1,2})月(\d{1,2})日", han)
    if m:
        mm, dd = int(m.group(1)), int(m.group(2))
        out |= {"{}月{}日".format(mm, dd), _to_zen("{}月{}日".format(mm, dd)),
                "{}/{}".format(mm, dd), "{}月{}日".format(mm, dd)}
    # trigram索引は3文字未満を引けない
    return sorted({t for t in out if len(t) >= 3})


def _expr(groups: List[List[str]]) -> str:
    """[[A,A'],[B]] → "(A OR A') AND (B)" 。FTS5 の式にする。"""
    def q(t: str) -> str:
        return '"' + t.replace('"', '""') + '"'
    parts = []
    for g in groups:
        g = [t for t in g if t]
        if not g:
            continue
        parts.append("(" + " OR ".join(q(t) for t in g) + ")" if len(g) > 1 else q(g[0]))
    return " AND ".join(parts)


def _rarity(conn, term: str) -> int:
    """その語を含むメール数。少ないほど「珍しい＝手がかりとして強い」。"""
    try:
        rows, total = db.search(conn, fts_expr=_expr([[term]]), limit=1)
        return total
    except Exception:      # noqa: BLE001 … 語が式として壊れていても止めない
        return 10 ** 9


def synonyms_of(term: str, use_llm: bool = True) -> List[str]:
    """言い換え。静的辞書 → 無ければ claude に聞く（落ちても空で返す）。"""
    if term in SYNONYMS:
        return SYNONYMS[term]
    if not use_llm:
        return []
    prompt = ("日本語のビジネスメールで「{}」とほぼ同じ意味で使われる言い換えを、"
              "**JSON配列だけ**で3つまで返してください。3文字以上の語だけ。"
              "説明は書かないこと。".format(term))
    try:
        proc = subprocess.run(
            [ai_query.CLAUDE_BIN, "-p", prompt, "--output-format", "json",
             "--dangerously-skip-permissions", "--model", "sonnet"],
            capture_output=True, text=True, timeout=45)
        outer = json.loads(proc.stdout)
        got = json.loads(ai_query._extract_json_array(outer.get("result", "")))
        return [str(x).strip() for x in got if len(str(x).strip()) >= 3][:3]
    except Exception:      # noqa: BLE001 … 言い換えが取れなくても検索は続ける
        return []


_ANSWER_PROMPT = """あなたはメールアーカイブの調査係です。利用者の質問に、**メールの中身を根拠に**
日本語で答えてください。

利用者の質問: {question}

見つかったメール（本文と、添付から取り出した文字）:
{items}

守ること:
- **質問に直接答える**。日時・場所・金額・締切など、聞かれていることを本文から拾って書く
- 根拠にしたメールを `[id=<番号>]` の形で必ず示す
- **添付にしか書かれていない事実は「添付〈ファイル名〉より」と明記する**
- 書いていないことは書かない。分からない項目は「メールには書かれていません」と述べる

出力は**JSONだけ**:
{{"answered": <true/false>, "answer": "<日本語の回答。要点は箇条書きでよい>",
  "ids": [<根拠にしたメールのid>]}}

`answered` は「**この材料で質問に答えられたか**」。
質問の条件（日付・場所・相手など）と食い違うメールしか無いなら **false** にすること。
false のときも、何が見つかったかは `answer` に書いてよい。
"""


def answer_from(question: str, items: List[Dict[str, Any]], timeout: int = 120) -> Dict[str, Any]:
    """候補メールを読ませて、質問への**答え**を書かせる。失敗したら RuntimeError。"""
    lines = []
    for it in items:
        lines.append("- id={} 日付={} 件名: {}\n  本文: {}".format(
            it["id"], (it.get("date") or "")[:10], it.get("subject") or "(なし)",
            " ".join((it.get("body") or "").split())[:1200]))
        for fname, text in (it.get("attachments") or []):
            lines.append("  添付〈{}〉: {}".format(fname, " ".join(text.split())[:1200]))
    prompt = _ANSWER_PROMPT.format(question=question.strip(), items="\n".join(lines))
    proc = subprocess.run(
        [ai_query.CLAUDE_BIN, "-p", prompt, "--output-format", "json",
         "--dangerously-skip-permissions", "--model", "sonnet"],
        capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError("claude が失敗しました（code {}）".format(proc.returncode))
    outer = json.loads(proc.stdout)
    if outer.get("is_error"):
        raise RuntimeError("Claude がエラーを返しました。")
    data = json.loads(ai_query._extract_json(outer.get("result", "")))
    return {"answered": bool(data.get("answered", True)),
            "answer": (data.get("answer") or "").strip(),
            "ids": [int(i) for i in (data.get("ids") or []) if str(i).isdigit()]}


def _rungs(conn, groups, dfrom, dto, extra, use_llm):
    """緩め方の階段を上から順に出す（必要になったときだけ計算する）。"""
    if groups:
        yield ("① 必須語で検索（表記ゆれも展開）", groups, dfrom, dto, "")
        if dfrom or dto:
            yield ("② 期間の指定を外して検索", groups, "", "",
                   "★指定の期間の外に見つかりました。期間を外して探しています。")
    # ③ ありふれた語から順に必須から外す（珍しい語を残す）
    if len(groups) >= 2:
        order = sorted(range(len(groups)), key=lambda i: -_rarity(conn, groups[i][0]))
        for drop in order:
            kept = [g for i, g in enumerate(groups) if i != drop]
            yield ("③ 「{}」を必須から外して検索".format(groups[drop][0]), kept, "", "",
                   "★「{}」を含むメールが無いので、条件から外して探しました。".format(groups[drop][0]))
    # ④ 言い換えを足す
    for i, g in enumerate(groups):
        syn = [s for s in synonyms_of(g[0], use_llm=use_llm) if len(s) >= 3]
        if not syn:
            continue
        widened = sorted(set(g) | set(syn))
        trial = [widened] + [x for j, x in enumerate(groups) if j != i]
        yield ("④ 「{}」の言い換えを足して検索（{}）".format(g[0], " / ".join(syn)),
               trial, "", "",
               "★言い換え（{}）で見つかりました。".format(" / ".join(syn)))
    # ⑤ 最後の網: どれか1語でも含むもの
    flat = sorted({t for g in groups for t in g} | {t for t in extra if len(t) >= 3})
    if flat:
        yield ("⑤ どれか1語でも含むもので検索", [flat], "", "",
               "★すべての語を含むメールは無いので、いずれかを含むもので探しました。")


def run(conn, question: str, max_hits: int = 20, use_llm: bool = True,
        on_step: Optional[Callable[[str], None]] = None,
        max_answers: int = 3) -> Dict[str, Any]:
    """自然文の質問に答える。戻り値は {answer, rows, tried, note}。

    **0件で終わらせない**、そして**1件見つかっただけでも終わらせない**のがこの関数の役目。

    ★後者は実際に踏んだ失敗（2026-08-31）。「9月2日のスイスホテルの懇親会」で
      ①が1件当たったが、それは**同じホテルの別の会（10/6の祝賀会）**だった。
      件数で満足せず「**その材料で質問に答えられたか**」を見て、駄目なら次の段へ進む。

    試したことは全部 `tried` に残す（何をどう試したかを見せないと利用者は納得できない）。
    """
    log: List[Dict[str, Any]] = []

    def step(label: str, expr: str, dfrom: str, dto: str):
        rows, total = db.search(conn, fts_expr=expr, date_from=dfrom, date_to=dto,
                                limit=max_hits)
        log.append({"やったこと": label, "条件": expr,
                    "期間": "{}〜{}".format(dfrom or "指定なし", dto or "指定なし"),
                    "件数": total})
        if on_step:
            on_step("{} → {}件".format(label, total))
        return rows, total

    # ---- 初手の条件（LLM。落ちても質問文から拾って続ける）
    plan: Dict[str, Any] = {"keywords_all": [], "keywords_any": [],
                            "date_from": "", "date_to": "", "explain": ""}
    if use_llm:
        try:
            plan = ai_query.parse_query(question)
        except Exception as e:      # noqa: BLE001
            log.append({"やったこと": "条件の自動解析に失敗（質問文から語を拾って続行）",
                        "条件": str(e)[:80], "期間": "", "件数": None})
    must = list(plan.get("keywords_all") or [])
    extra = list(plan.get("keywords_any") or [])
    dfrom, dto = plan.get("date_from") or "", plan.get("date_to") or ""

    # ★質問文に出てくる日付は**必須語として**拾い直す（2026-08-31 の反省点）。
    #   従来は期間表現しか見ておらず「9月2日」を丸ごと捨てていた。本文に書かれた開催日は
    #   最も強い手がかりなので、まずANDに入れる。当たらなければ③の段で自動的に外れる。
    import semantic
    for d in _dates_in(question):
        if d not in must:
            must.append(d)
    for t in semantic.query_content_terms(question):
        if t not in must and t not in extra:
            extra.append(t)

    groups = [term_variants(t) for t in must] or [term_variants(t) for t in extra[:2]]

    # 画面で「📎 添付のどこに当たったか」を出すために、使った語を返り値に載せる
    used_terms = sorted({t for g in groups for t in g} | {t for t in extra if len(t) >= 3})

    best: Optional[Dict[str, Any]] = None
    judged = 0
    for label, g, df, dt, note in _rungs(conn, groups, dfrom, dto, extra, use_llm):
        rows, total = step(label, _expr(g), df, dt)
        if not total:
            continue
        if not use_llm or judged >= max_answers:
            return {"answer": "", "rows": rows, "tried": log, "note": note,
                    "ids": [], "terms": used_terms}
        got = _judge(conn, question, rows)
        judged += 1
        if got and got.get("answered"):
            log[-1]["評価"] = "質問に答えられた"
            return {"answer": got["answer"], "rows": rows, "tried": log,
                    "note": note, "ids": got["ids"], "terms": used_terms}
        # ★見つかったが質問には合っていない → **止めずに次の段へ**
        log[-1]["評価"] = "見つかったが質問には合わない（探索を続ける）"
        if on_step:
            on_step("　→ 質問には合わないので、条件を変えて続けます")
        if best is None:
            best = {"answer": (got or {}).get("answer", ""), "rows": rows,
                    "note": note, "ids": (got or {}).get("ids", []), "terms": used_terms}

    if best:
        best["tried"] = log
        best["note"] = ((best.get("note") or "") +
                        " ／ ★質問にぴったり合うメールは見つかりませんでした（近いものを出しています）")
        return best
    return {"answer": "", "rows": [], "tried": log, "ids": [], "terms": used_terms,
            "note": "見つかりませんでした。試した条件は下に出しています。"}


def _judge(conn, question: str, rows) -> Optional[Dict[str, Any]]:
    """候補を読ませて、答えが書けるか判定する。失敗しても検索は続ける。"""
    items = []
    for r in rows[:6]:
        atts = [(a["filename"], a["text"]) for a in db.attachment_texts_of(conn, r["id"])]
        items.append({"id": r["id"], "date": r["date_utc"], "subject": r["subject"],
                      "body": r["body_text"] or "", "attachments": atts})
    try:
        return answer_from(question, items)
    except Exception:      # noqa: BLE001
        return None


def _dates_in(text: str) -> List[str]:
    """質問文に出てくる日付を拾う（「9月2日」「9/2」）。**期間ではなく検索語**として使う。"""
    t = _to_han(text or "")
    out = []
    for m in re.finditer(r"(\d{1,2})月(\d{1,2})日", t):
        out.append("{}月{}日".format(int(m.group(1)), int(m.group(2))))
    return out


def main() -> int:
    import config
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    question = " ".join(sys.argv[1:])
    conn = db.connect(config.DB_PATH)
    res = run(conn, question, on_step=lambda s: print("  " + s, flush=True))
    print("\n=== 試したこと ===")
    for t in res["tried"]:
        print("  {} … {}件".format(t["やったこと"], t["件数"]))
        print("      {}  期間 {}".format(t["条件"][:100], t["期間"]))
    if res.get("note"):
        print("\n" + res["note"])
    print("\n=== 答え ===")
    print(res["answer"] or "(答えは作れませんでした)")
    print("\n=== 根拠のメール ===")
    for r in res["rows"][:5]:
        mark = "★" if r["id"] in (res.get("ids") or []) else " "
        print("  {}[{}] {} {}".format(mark, r["id"], (r["date_utc"] or "")[:10],
                                      (r["subject"] or "")[:60]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
