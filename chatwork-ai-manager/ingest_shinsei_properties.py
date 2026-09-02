#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""新誠プロパティマネジメントの所有物件マスターを作る（2026-09-02）。

出所（GoogleDrive/マイドライブ/新誠プロパティ/）:
  ★所有物件台帳.xlsx   … 物件23件。名前・市・所在・地番・地積・床面積・取得日・簿価・
                          利用状況（賃貸中/空き/活用中）・月額賃料・固定資産税評価額
  ★レントロール入金管理.xls … 年ごとのシート(R2〜R8)。場所・区画タイプ・契約者・金額と、
                          1〜12月の入金欄

**なぜ `properties`（大京商事のマスター）に混ぜないのか**（再検討しないための記録）:
  `properties` を読む場所は6ファイル14か所に散っている（gis.py / agent_tools/gis_tools.py /
  views/property_map.py / services/property_master.py / fix_image_titles.py /
  ingest_properties.py）。会社の列を足す案は、**その全部を漏れなく絞り込まないと
  大京の画面へ新誠が黙って出る**——気づけない形で会社の壁が破れる。別テーブルなら
  直すのは名寄せの2関数だけで、失敗しても「新誠の物件が見つからない」という
  目に見える形で止まる。列の中身も違い、台帳13列のうち `properties` に素で入るのは2列だけ。

**入金欄の記号**（2026-09-02 オーナー確認。凡例はファイルのどこにも無い）:
  〇 … その月の入金あり
  ● … **退去の最終月**
  したがって「最後の印が ● なら現在は空室」「● のあとに 〇 が続くなら次の入居者が入った」。
  実データ5件すべてで台帳の利用状況と一致することを確認済み。
  ★契約者欄には**最新の1名しか入っていない**ので、● より前の 〇 は別の人の分。
  ここから過去の入居者は復元できない（名前が残っていない）。

呼び名の揺れ（aliases）の作り方——**推測しない**:
  1. 機械的な変換だけ: 全角数字→半角、「戸建て」を落とす（秋津戸建て２ → 秋津2）
  2. 過去年のシートとの突き合わせ: **契約者名と区画タイプが一致する行**だけを同一物件とみなす
     （加東2 → 秋津戸建て２ 等）。金額や場所名の似ている・いないでは判断しない。

使い方:
    /usr/bin/python3 ingest_shinsei_properties.py          # 取込
    /usr/bin/python3 ingest_shinsei_properties.py --show   # 取込結果を見るだけ
"""
from __future__ import annotations

import argparse
import collections
import os
import re
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from db.connection import get_conn, query  # noqa: E402

DRIVE = ("/Users/apple/Library/CloudStorage/GoogleDrive-daikyocorp.s@gmail.com/"
         "マイドライブ/新誠プロパティ/")
LEDGER = DRIVE + "★所有物件台帳.xlsx"
RENTROLL = DRIVE + "★レントロール入金管理.xls"

COMPANY = "新誠プロパティマネジメント株式会社"

PAID, LEFT = "〇", "●"          # 入金あり / 退去の最終月

# ★この2ファイルに入っていない物件（2026-09-02 オーナー確認）。
#
# **吹田岸部だけは別会社（株式会社リンク建物管理）に管理を委託していて、
# レントロールでは入金管理をしていない。** 代わりに毎月「月次報告書」がメールで届く
# （大塚稔朗 otsukalink@gmail.com・毎月7〜10日ごろ・添付は送金明細書のPDF）。
#
# ★契約者は**ここに書かない**。`ingest_shinsei_payouts.py` がメールアーカイブから
#   最新の明細を読んで入れる。ここでベタ書きすると毎月古くなるため。
#   ここで持つのは**呼び名だけ**（明細書は「シェローバイクパーク吹田岸部」と書くが、
#   台帳は「SBP岸辺中」。岸辺／岸部で字も違う）。
EXTERNAL_ALIASES = {
    "SBP岸辺中": ["シェローバイクパーク吹田岸部", "吹田岸部", "吹田岸辺"],
}


def _n(s) -> str:
    """比較用の正規化（全角半角・空白の揺れを吸収）。"""
    return unicodedata.normalize("NFKC", str(s or "")).replace(" ", "").strip()


# ------------------------------------------------------------------ 台帳
def read_ledger() -> list[dict]:
    import openpyxl
    wb = openpyxl.load_workbook(LEDGER, data_only=True)
    ws = wb["所有物件"]
    out = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if not r[1]:
            continue
        def s(v):
            return "" if v is None else str(v).strip()
        city, town, lot = s(r[2]), s(r[3]), s(r[4])
        out.append({
            "no": int(r[0]) if r[0] else None,
            "name": s(r[1]),
            "city": city, "town": town, "lot": lot,
            "address": f"{city}{town}{lot}".strip(),
            "land_area": s(r[5]), "floor_area": s(r[6]), "acquired": s(r[7]),
            "land_book": s(r[8]), "building_book": s(r[9]),
            "status": s(r[10]), "rent": s(r[11]), "tax_value": s(r[12]),
        })
    return out


# ------------------------------------------------------------------ レントロール
def read_rentroll() -> dict[str, list[dict]]:
    """年シート名 → 行のリスト。"""
    import xlrd
    wb = xlrd.open_workbook(RENTROLL)
    years = {}
    for name in wb.sheet_names():
        if not re.fullmatch(r"R\d+", name):
            continue
        sh = wb.sheet_by_name(name)
        rows = []
        for i in range(1, sh.nrows):
            v = [c.value for c in sh.row(i)]
            place = str(v[0]).strip()
            if not place:
                continue
            marks = [str(x).strip() for x in v[4:16]]
            rows.append({"place": place, "type": str(v[1]).strip(),
                         "tenant": str(v[2]).strip(), "amount": v[3], "marks": marks})
        years[name] = rows
    return years


def latest_year(years: dict) -> str:
    return max(years, key=lambda k: int(k[1:]))


def occupancy(marks: list[str]) -> tuple[str, int | None]:
    """入金欄から現況を読む。戻り: (状態, 最後に印が付いた月)。

    `●` は退去の最終月なので、**最後の印が ● なら現在は空室**。
    `●` のあとに `〇` が続くなら次の入居者が入っている＝入居中。
    """
    last_i = last_v = None
    for i, m in enumerate(marks):
        if m:
            last_i, last_v = i + 1, m
    if last_v is None:
        return "記録なし", None
    # 〇 と ○ は別の文字（U+3007 / U+25CB）が混在している。どちらも入金ありとして扱う
    return ("空室（退去済み）" if last_v == LEFT else "入居中"), last_i


# ------------------------------------------------------------------ 呼び名の揺れ
_KANSUJI = str.maketrans("０１２３４５６７８９", "0123456789")


def mechanical_aliases(name: str) -> set[str]:
    """名前そのものから機械的に作れる呼び名だけ（推測は入れない）。"""
    out = set()
    half = name.translate(_KANSUJI)
    out.add(half)
    for base in (name, half):
        short = base.replace("戸建て", "").replace("戸建", "")
        if short and short != base:
            out.add(short)
    return {a for a in out if a and a != name}


def derived_aliases(years: dict) -> dict[str, set[str]]:
    """過去年のシートから、**契約者名と区画タイプが一致する行**だけを同一物件とみなす。

    場所名の字面（「加東2」と「秋津戸建て２」）はまったく似ていないので、
    文字列の類似では対応づけられない。人と区画で結ぶ。
    """
    cur = latest_year(years)
    key_to_place = {(_n(r["tenant"]), _n(r["type"])): r["place"]
                    for r in years[cur] if r["tenant"]}
    out = collections.defaultdict(set)
    for y, rows in years.items():
        if y == cur:
            continue
        for r in rows:
            k = (_n(r["tenant"]), _n(r["type"]))
            place = key_to_place.get(k)
            if place and _n(place) != _n(r["place"]):
                out[place].add(r["place"])
    return out


# ------------------------------------------------------------------ 取込
COLS = ["property_id", "no", "name", "aliases", "city", "town", "lot", "address",
        "land_area", "floor_area", "acquired", "land_book", "building_book",
        "status", "rent", "tax_value", "tenant", "tenant_as_of", "tenant_source"]

# レントロールのシート名（R8＝令和8年）を人が読む形に
LATEST_YEAR_LABEL = {f"R{n}": f"令和{n}年" for n in range(1, 20)}


def drop_ambiguous(records: list[dict]) -> int:
    """**他の物件と取り違える呼び名を捨てる。** 消した件数を返す。

    実データで見つかった危険（2026-09-02）:
      「三田」… 西相野戸建ての呼び名として出てくるが、**三田市には他に3物件ある**
                （大川瀬戸建て・グリーンログ大川瀬・グリーンガーデン大川瀬）。
                これを残すと「三田の物件」の一言で西相野に決め打ちしてしまう。
    判定は「その呼び名が2つ以上の物件の市名に含まれるか」。市の名前は物件を特定しない。
    """
    cities = [r["city"] for r in records if r["city"]]
    dropped = 0
    for r in records:
        keep = []
        for a in (r["aliases"] or "").split("\n"):
            if not a:
                continue
            if sum(1 for c in cities if a in c) >= 2:
                dropped += 1
                continue
            keep.append(a)
        r["aliases"] = "\n".join(keep)
    return dropped


def build() -> list[dict]:
    ledger = read_ledger()
    years = read_rentroll()
    cur = latest_year(years)
    derived = derived_aliases(years)

    by_place = collections.defaultdict(list)
    for r in years[cur]:
        by_place[_n(r["place"])].append(r)

    out = []
    for L in ledger:
        units = by_place.get(_n(L["name"]), [])
        aliases = mechanical_aliases(L["name"])
        for a in derived.get(L["name"], set()):
            aliases.add(a)
        # 契約者は「区画タイプ:名前（現況）」を並べる。駐車場は1物件に複数区画ある
        tenants = []
        for u in units:
            state, _m = occupancy(u["marks"])
            label = f"{u['type']}:{u['tenant']}" if u["type"] else u["tenant"]
            tenants.append(f"{label}（{state}）")
        aliases |= set(EXTERNAL_ALIASES.get(L["name"], []))
        rec = {c: L.get(c, "") for c in COLS}
        rec["property_id"] = _n(L["name"])
        rec["name"] = L["name"]
        rec["aliases"] = "\n".join(sorted(aliases))
        rec["tenant"] = " / ".join(tenants)
        rec["tenant_as_of"] = LATEST_YEAR_LABEL.get(cur, cur) if tenants else ""
        rec["tenant_source"] = "★レントロール入金管理.xls" if tenants else ""
        out.append(rec)
    dropped = drop_ambiguous(out)
    if dropped:
        print(f"（取り違えの危険がある呼び名を {dropped} 件外しました）")
    return out


def save(records: list[dict]) -> dict:
    seen = [r["property_id"] for r in records]
    created = updated = 0
    with get_conn() as conn:
        existing = {r["property_id"] for r in query("SELECT property_id FROM shinsei_properties")}
        for r in records:
            vals = [r[c] for c in COLS]
            if r["property_id"] in existing:
                # ★契約者が空のときは tenant 系を上書きしない。
                #   レントロールに載らない物件（吹田岸部）は送金明細書から入るので、
                #   ここで空文字を書くと毎回それを消してしまう
                cols = COLS[1:] if r["tenant"] else [
                    c for c in COLS[1:] if not c.startswith("tenant")]
                conn.execute(
                    "UPDATE shinsei_properties SET "
                    + ", ".join(f"{c}=?" for c in cols)
                    + ", active=1, updated_at=datetime('now','localtime') WHERE property_id=?",
                    [r[c] for c in cols] + [r["property_id"]])
                updated += 1
            else:
                conn.execute(
                    f"INSERT INTO shinsei_properties ({', '.join(COLS)}) "
                    f"VALUES ({', '.join('?' * len(COLS))})", vals)
                created += 1
        if seen:
            ph = ", ".join("?" * len(seen))
            conn.execute(
                f"UPDATE shinsei_properties SET active=0 WHERE property_id NOT IN ({ph})", seen)
    return {"created": created, "updated": updated, "total": len(records)}


def show():
    rows = query("SELECT * FROM shinsei_properties WHERE active=1 ORDER BY no")
    print(f"新誠プロパティ 所有物件マスター: {len(rows)}件\n")
    for r in rows:
        al = (r["aliases"] or "").replace("\n", " / ")
        print(f"{r['no']:>3}. {r['name']}  [{r['status']}]")
        print(f"     住所   : {r['address']}")
        print(f"     呼び名 : {al or '（なし）'}")
        src = f"  〔{r['tenant_source']}・{r['tenant_as_of']}時点〕" if r["tenant"] else ""
        print(f"     契約者 : {r['tenant'] or '（記載なし）'}{src}")


def main():
    ap = argparse.ArgumentParser(description="新誠プロパティの所有物件マスターを作る")
    ap.add_argument("--show", action="store_true", help="取込済みの内容を表示するだけ")
    args = ap.parse_args()
    if args.show:
        show()
        return
    for p in (LEDGER, RENTROLL):
        if not os.path.exists(p):
            print(f"見つかりません: {p}\n"
                  "※ GoogleDrive(CloudStorage) は launchd からは読めません。"
                  "ターミナルから実行してください。")
            sys.exit(1)
    from db.migrate import migrate
    migrate()
    res = save(build())
    print(f"取込: 新規 {res['created']} / 更新 {res['updated']} / 合計 {res['total']}")
    show()


if __name__ == "__main__":
    main()
