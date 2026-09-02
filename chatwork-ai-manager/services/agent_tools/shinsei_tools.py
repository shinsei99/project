# -*- coding: utf-8 -*-
"""新誠プロパティマネジメントの所有物件（23件）を引く道具（2026-09-02）。

大京商事の管理物件（`properties` / `gis_property_*`）とは**別のマスター**を見る。
理由は `ingest_shinsei_properties.py` の冒頭にある。

★会社の壁: **新誠の場（鷲見さん個人チャット）からしか使えない。**
  他社の場から呼ばれたら、中身を一切返さずに断る。
"""
from services import company_scope as CS
from services import shinsei_properties as SP

_FIELDS = ("no", "name", "aliases", "status", "address", "city", "town", "lot",
           "land_area", "floor_area", "acquired", "rent", "tenant",
           "land_book", "building_book", "tax_value")


def _deny():
    return {"ok": False,
            "error": ("新誠プロパティの所有物件は、新誠の場（鷲見さんとのダイレクトチャット）"
                      "でのみ参照できます。ここは「%s」の場です。"
                      % (CS.here() or "不明"))}


def _pick(row, full=False):
    keys = _FIELDS if full else ("no", "name", "status", "address", "rent", "tenant")
    d = {k: row.get(k) for k in keys}
    if d.get("aliases"):
        d["aliases"] = [a for a in row["aliases"].split("\n") if a]
    return d


def shinsei_property_list(status=None, keyword=None):
    """新誠プロパティの所有物件一覧（23件）。status で「空き」「賃貸中」「活用中」に絞れる。"""
    if CS.here() != SP.COMPANY:
        return _deny()
    rows = SP.all_properties()
    if status:
        rows = [r for r in rows if status in (r.get("status") or "")]
    if keyword:
        k = keyword.strip()
        rows = [r for r in rows
                if k in (r.get("name") or "") or k in (r.get("address") or "")
                or k in (r.get("aliases") or "") or k in (r.get("tenant") or "")]
    return {"ok": True, "count": len(rows), "properties": [_pick(r) for r in rows]}


def shinsei_property_detail(name):
    """物件1件の詳細（呼び名・台帳の全項目・区画ごとの契約者）。呼び名でも引ける。"""
    if CS.here() != SP.COMPANY:
        return _deny()
    r = SP.find(name)
    if not r:
        return {"ok": False, "error": f"見つかりません: {name}",
                "hint": "shinsei_property_list で一覧を見てください"}
    return {"ok": True, "property": _pick(r, full=True)}


def shinsei_tenants(name=None):
    """契約者の一覧。name を省くと全物件ぶんを並べる。

    ★空室の見分け方: 「（空室（退去済み））」と付いている名前は**退去した人**。
      レントロールの契約者欄には最新の1名しか残らないため、それより前の入居者は分からない。
    """
    if CS.here() != SP.COMPANY:
        return _deny()
    rows = [SP.find(name)] if name else SP.all_properties()
    rows = [r for r in rows if r]
    if not rows:
        return {"ok": False, "error": f"見つかりません: {name}"}
    out, live, vac = [], 0, 0
    for r in rows:
        units = [u for u in (r.get("tenant") or "").split(" / ") if u and not u.startswith("※")]
        note = next((u for u in (r.get("tenant") or "").split(" / ") if u.startswith("※")), None)
        live += sum(1 for u in units if "空室" not in u)
        vac += sum(1 for u in units if "空室" in u)
        out.append({"name": r["name"], "status": r.get("status"),
                    "units": units or None, "note": note})
    return {"ok": True, "count": len(out), "契約中": live, "空き": vac, "properties": out}
