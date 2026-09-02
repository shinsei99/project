#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""管理委託先から毎月届く「送金明細書」を読んで、新誠の契約者を最新にする（2026-09-02）。

**なぜ要るのか**: 所有23件のうち **吹田岸部（台帳名 SBP岸辺中）だけ**は別会社に管理を
委託していて、`★レントロール入金管理.xls` に入金記録が無い。代わりに毎月

    株式会社リンク建物管理・大塚稔朗（otsukalink@gmail.com）
    件名「◯月月次報告書」／添付「新誠プロパティマネジメント様.pdf」＝送金明細書

がメールで届く（毎月7〜10日ごろ）。**放置すると契約者が古くなる**ので、
メールアーカイバ（8535）が既に取り込んでいる添付本文から自動で読み直す。

読むもの・読まないもの:
- **`mail-archiver/local/mail.db` を読むだけ**（書き込まない）。しかも
  **差出人を `otsukalink@gmail.com` に限定**する。個人メール全体は開かない。
- PDF は**スキャンのOCRテキスト**なので崩れる（実測: 「定率18,000円×7%＋税」→
  「定年18,000円✕1%+*」）。**正規表現で読まず claude に構造化させる**。
  金額は使わない——契約者と空室だけ取る。金額はOCRの誤りが致命的になるため。

★**新誠の物件としてメールで来るのは吹田岸部だけ**（2026-09-02 オーナー確認）。
同じ差出人から鶴見徳庵・玉出インター前の明細も届くが、**あれは大京商事の案件**なので
**新誠のマスターへ入れてはいけない**（会社の壁）。実装は「新誠のマスターに名前が
当たった物件だけ書き込む」＝吹田岸部だけが通る形にしてある。
**当たらなかった物件は黙って捨てず必ず報告する**が、それは「マスターに足せ」という
意味ではない。足すと壁を越える。

使い方:
    /usr/bin/python3 ingest_shinsei_payouts.py            # 最新分を取り込む
    /usr/bin/python3 ingest_shinsei_payouts.py --list     # 届いている明細を一覧するだけ
    /usr/bin/python3 ingest_shinsei_payouts.py --dry-run  # 読むだけで書かない
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_conn  # noqa: E402

MAIL_DB = "/Users/apple/mail-archiver/local/mail.db"
SENDER = "otsukalink@gmail.com"          # 株式会社リンク建物管理・大塚稔朗
SOURCE_LABEL = "リンク建物管理 送金明細書"

PROMPT = """次は、管理会社から届いた「送金明細書」PDF から取り出した文字です。
スキャンをOCRしたものなので、崩れている箇所があります。

ここから **物件ごとの区画（部屋）と契約者** だけを読み取り、JSON で返してください。
**金額は読み取らないでください**（OCRの誤りが多いため使いません）。

- `※※〜※※` で囲まれた行が物件名です（例: `※※シェローバイクパーク吹田岸部※※`）
- その下に「区画名＋契約者名」が続きます。**区切り文字が無く繋がっています**
  （例: `ポータブル1村上太一` → 区画「ポータブル1」・契約者「村上太一」）
- `※※ 空室 ※※` と書かれた区画は空室です（契約者は空）
- 「収入合計」「控除」「管理手数料」「送金額合計」などの集計行は**区画ではありません**。除いてください
- 該当年月（例 `2026/08`）を `as_of` に入れてください

次の形だけを出力してください（前置き・説明・コードフェンスは不要）:

{"as_of": "2026/08", "properties": [
  {"name": "シェローバイクパーク吹田岸部",
   "units": [{"unit": "ポータブル1", "tenant": "村上太一", "vacant": false},
             {"unit": "ポータブル3", "tenant": "", "vacant": true}]}
]}

----- 明細書の文字 -----
%s
"""


def reports(limit: int | None = None) -> list[dict]:
    """メールアーカイブから送金明細書の添付本文を新しい順に取り出す（読むだけ）。"""
    if not os.path.exists(MAIL_DB):
        raise SystemExit(f"メールアーカイブが見つかりません: {MAIL_DB}")
    # 読み取り専用で開く（他アプリのDBなので絶対に書かない）
    conn = sqlite3.connect(f"file:{MAIL_DB}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT DISTINCT m.date_utc, m.subject, a.filename, t.text "
        "FROM attachment_texts t "
        "JOIN attachments a ON a.id = t.attachment_id "
        "JOIN messages m ON m.id = a.message_id "
        "WHERE m.from_addr = ? AND t.text IS NOT NULL AND t.text != '' "
        "ORDER BY m.date_utc DESC", (SENDER,)).fetchall()
    conn.close()
    out, seen = [], set()
    for r in rows:
        key = (r["date_utc"][:7], r["filename"])       # 同じ月の重複添付は1つでよい
        if key in seen:
            continue
        seen.add(key)
        out.append(dict(r))
        if limit and len(out) >= limit:
            break
    return out


def parse(text: str) -> dict | None:
    """claude に構造化させる。OCR崩れがあるので正規表現では読まない。"""
    from services.claude_client import ClaudeError, run_text
    try:
        raw, _env = run_text(PROMPT % text[:12000], model="sonnet", timeout=180)
    except ClaudeError as e:
        print(f"  claude 呼び出しに失敗: {e}")
        return None
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
    try:
        return json.loads(raw)
    except Exception:
        print(f"  JSONとして読めませんでした: {raw[:200]}")
        return None


def apply(parsed: dict, dry_run: bool = False) -> dict:
    """読み取った内容を shinsei_properties へ入れる。マスターに無い物件は報告する。"""
    from services import shinsei_properties as SP
    as_of = (parsed.get("as_of") or "").strip()
    updated, unmatched, skipped = [], [], []
    for p in parsed.get("properties") or []:
        name = (p.get("name") or "").strip()
        row = SP.find(name)
        if not row:
            # 新誠の所有物件に当たらない＝大京の案件。ここで止まるのが正しい
            unmatched.append(name)
            continue
        parts = []
        for u in p.get("units") or []:
            unit = (u.get("unit") or "").strip()
            who = (u.get("tenant") or "").strip()
            if u.get("vacant") or not who:
                parts.append(f"{unit}:（空室）")
            else:
                parts.append(f"{unit}:{who}（入居中）")
        if not parts:
            continue
        # ★古い明細で新しい明細を上書きしない（2026-09-02）。
        #   --months 2 以上だと古い順に書き込んでしまい、6月分が8月分を潰した（実測）
        have = (row.get("tenant_as_of") or "").strip()
        if have and as_of and as_of < have:
            skipped.append(f"{row['name']}（{as_of} は既にある {have} より古い）")
            continue
        if not dry_run:
            with get_conn() as conn:
                conn.execute(
                    "UPDATE shinsei_properties SET tenant=?, tenant_as_of=?, tenant_source=?, "
                    "updated_at=datetime('now','localtime') WHERE property_id=?",
                    (" / ".join(parts), as_of, SOURCE_LABEL, row["property_id"]))
        updated.append({"master": row["name"], "as_of": as_of, "units": parts})
    return {"as_of": as_of, "updated": updated, "unmatched": unmatched,
            "skipped": skipped}


def main():
    ap = argparse.ArgumentParser(description="送金明細書から新誠の契約者を最新にする")
    ap.add_argument("--list", action="store_true", help="届いている明細を一覧するだけ")
    ap.add_argument("--dry-run", action="store_true", help="読むだけで書き込まない")
    ap.add_argument("--months", type=int, default=1,
                    help="新しい方から何か月ぶん読むか（既定1＝最新のみ）")
    args = ap.parse_args()

    rs = reports()
    if args.list:
        print(f"{SENDER} からの明細: {len(rs)}件")
        for r in rs:
            print("  ", r["date_utc"][:10], "|", (r["subject"] or "")[:24], "|", r["filename"])
        return
    if not rs:
        print("送金明細書が見つかりません（メールアーカイバの取込がまだかもしれません）")
        return

    from db.migrate import migrate
    migrate()
    for r in rs[:max(1, args.months)]:
        print(f"■ {r['date_utc'][:10]}  {r['subject']}")
        parsed = parse(r["text"])
        if not parsed:
            continue
        res = apply(parsed, dry_run=args.dry_run)
        for u in res["updated"]:
            print(f"  → {u['master']}（{u['as_of']}時点）")
            for x in u["units"]:
                print(f"       {x}")
        for n in res.get("skipped") or []:
            print(f"  － 古いので飛ばしました: {n}")
        for n in res["unmatched"]:
            # ★これは異常ではない。同じ差出人から**大京商事の案件**（鶴見徳庵・
            #   玉出インター前）も届くため。**新誠のマスターへ足してはいけない。**
            print(f"  － 新誠の物件ではないので取り込みません（大京の案件）: {n}")
    if args.dry_run:
        print("\n（--dry-run なので書き込んでいません）")


if __name__ == "__main__":
    main()
