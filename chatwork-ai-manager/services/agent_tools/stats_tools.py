"""政府統計（e-Stat）のTool。**商圏の客観データ**をAIが自分で引けるようにする。

実体は**直下の共有クライアント `estat_api.py`**（他アプリと同じ1本。コピーを作らない）。
appId は直下 `.env.estat`（gitignore）。標準ライブラリだけで動く（requests 不要）。

何に効くか:

- 「この物件のあたり、賃貸需要ある？」… 世帯数・単身が多いか・転入超過か・将来推計
- 「都島区と旭区、どっちが空き家多い？」… 空き家率・借家率を区どうしで並べる
- オーナーへの提案・買取判断の**根拠になる公的な数字**（社内資料の肌感覚と突き合わせる）

数字の出どころは国勢調査（5年おき）・住宅土地統計調査（5年おき・最新2023年）・
住民基本台帳・建築着工統計。**必ず「何年の値か」を一緒に返す**ので、回答にも年を書くこと。

はまり所（2026-08-23 実測）:
  - 統計は**市区町村単位**。町丁目や「駅から徒歩10分」の粒度は無い。
    番地まで含む住所を渡しても、返るのはその市区町村の値
  - 項目ごとに調査年が違う（人口2020年・住宅2023年・着工は毎年）。
    割合を出すときは分母と分子の年が揃っているかを見て、違えば注記を付けている
  - 政令市の「区」は独立したコードを持つ（大阪市都島区=27102）。市全体を見たいときは 27100
"""
import pathlib
import sys

from services import gis

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# 人口・世帯（Ａ表）で使う項目
_POP_CATS = [
    "A1101",  # 総人口
    "A1301",  # 15歳未満人口
    "A1303",  # 65歳以上人口
    "A1700",  # 外国人人口
    "A7101",  # 世帯数
    "A710101",  # 一般世帯数
    "A710201",  # 一般世帯人員数
    "A5103",  # 転入者数
    "A5104",  # 転出者数
    "A6107",  # 昼間人口
    "A6108",  # 昼夜間人口比率
    "A191003",  # 将来推計人口（2030年）
    "A191005",  # 将来推計人口（2040年）
]

# 居住（Ｈ表）で使う項目
_HOUSING_CATS = [
    "H1100",    # 総住宅数
    "H1101",    # 居住世帯あり住宅数
    "H110202",  # 空き家数
    "H1310",    # 持ち家数
    "H1320",    # 借家数
    "H1322",    # 民営借家数
    "H1403",    # 共同住宅数
    "H1802",    # 着工新設貸家数
    "H2130",    # 1住宅当たり延べ面積
    "H213020",  # 1住宅当たり延べ面積（借家）
]


def _import():
    import estat_api  # 直下の共有クライアント
    return estat_api


def _fmt(value, unit=""):
    if value is None:
        return "—"
    if isinstance(value, int):
        return "{:,}{}".format(value, unit)
    return "{:,.1f}{}".format(value, unit)


def _resolve_area(estat, city_code=None, property=None, address=None, city=None):
    """市区町村コード（5桁）と、どうやって決めたかを返す。"""
    if city_code:
        code = estat.normalize_area(city_code)
        if not code:
            return None, None, "市区町村コードは5桁の数字で渡してください: {}".format(city_code)
        return code, "市区町村コード {}".format(code), None

    if property:
        p = gis.find_property(property)
        if not p:
            return None, None, "物件が見つかりません: {}".format(property)
        if p.get("lat") is None:
            return None, None, "座標が未取得の物件です: {}".format(p["name"])
        code = estat.muni_code(p["lat"], p["lon"])
        if not code:
            return None, None, "物件の座標から市区町村コードを特定できませんでした: {}".format(p["name"])
        return code, "物件「{}」（{}）".format(p["name"], p.get("address") or ""), None

    query = address or city
    if query:
        g = gis.geocode(query)
        if not g.get("ok"):
            return None, None, "住所・地名から座標を特定できません: {}".format(query)
        code = estat.muni_code(g["lat"], g["lon"])
        if not code:
            return None, None, "座標から市区町村コードを特定できませんでした: {}".format(query)
        return code, query, None

    return None, None, "property / address / city / city_code のいずれかを指定してください"


def _collect(estat, table, targets, cats):
    """[(コード, 指定のしかた)] → e-Stat から1回で引いて整形する。"""
    codes = [t[0] for t in targets]
    data = estat.get_values(table, codes, cats)
    out = []
    for code, label in targets:
        area = data["areas"].get(code, {})
        out.append({
            "city_code": code,
            "city": area.get("name") or label,
            "asked_as": label,
            "values": area.get("values", {}),
        })
    return out


def _ratio(values, numerator, denominator):
    """割合（%）と、分子・分母の調査年。年が食い違うときは note を付ける。"""
    num = values.get(numerator)
    den = values.get(denominator)
    if not num or not den or not den.get("value"):
        return None
    pct = round(num["value"] / den["value"] * 100, 1)
    row = {"percent": pct, "year": num.get("year", "")}
    if num.get("year") != den.get("year"):
        row["note"] = "分子{}年・分母{}年の値から計算".format(num.get("year"), den.get("year"))
    return row


def _pick(values, code):
    slot = values.get(code)
    if not slot:
        return None
    return {"value": slot["value"], "unit": slot["unit"], "year": slot["year"]}


def estat_area_profile(property=None, address=None, city=None, city_code=None, compare=None):
    """商圏の人口・世帯（e-Stat 社会・人口統計体系）。compare に地名/コードを並べると比較できる。"""
    try:
        estat = _import()
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    targets = []
    code, label, err = _resolve_area(estat, city_code, property, address, city)
    if err:
        return {"ok": False, "error": err}
    targets.append((code, label))

    for other in (compare or []):
        other = str(other).strip()
        if not other:
            continue
        if other.isdigit():
            c, l, e2 = _resolve_area(estat, city_code=other)
        else:
            c, l, e2 = _resolve_area(estat, city=other)
        if e2:
            return {"ok": False, "error": e2}
        targets.append((c, l))

    try:
        rows = _collect(estat, "population", targets, _POP_CATS)
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    out = []
    lines = []
    for row in rows:
        v = row["values"]
        pop = _pick(v, "A1101")
        item = {
            "city_code": row["city_code"],
            "city": row["city"],
            "asked_as": row["asked_as"],
            "人口": pop,
            "世帯数": _pick(v, "A7101"),
            "一般世帯数": _pick(v, "A710101"),
            "外国人人口": _pick(v, "A1700"),
            "転入者数": _pick(v, "A5103"),
            "転出者数": _pick(v, "A5104"),
            "昼夜間人口比率": _pick(v, "A6108"),
            "高齢化率": _ratio(v, "A1303", "A1101"),
            "年少人口比率": _ratio(v, "A1301", "A1101"),
            "将来推計人口2030": _pick(v, "A191003"),
            "将来推計人口2040": _pick(v, "A191005"),
        }
        # 1世帯あたり人員は「一般世帯人員 ÷ 一般世帯数」が正しい（施設等の世帯を混ぜない）
        members = v.get("A710201")
        households = v.get("A710101")
        if members and households and households.get("value"):
            item["1世帯あたり人員"] = {
                "value": round(members["value"] / households["value"], 2),
                "unit": "人", "year": members.get("year", ""),
            }
        # 社会増減（転入 − 転出）
        in_, out_ = v.get("A5103"), v.get("A5104")
        if in_ and out_:
            item["社会増減"] = {
                "value": in_["value"] - out_["value"], "unit": "人",
                "year": in_.get("year", ""),
                "note": "プラスなら転入超過（賃貸需要の向きを見る目安）",
            }
        # 将来推計の増減率（基準は最新の総人口）
        future = v.get("A191005")
        if future and pop and pop.get("value"):
            item["2040年の人口増減率"] = {
                "percent": round((future["value"] - pop["value"]) / pop["value"] * 100, 1),
                "note": "{}年の総人口を100としたときの2040年推計".format(pop.get("year")),
            }
        out.append(item)

        lines.append("■ {}".format(item["city"]))
        if pop:
            lines.append("  人口 {}（{}年）／世帯数 {}".format(
                _fmt(pop["value"], "人"), pop["year"],
                _fmt((item["世帯数"] or {}).get("value"), "世帯")))
        if item.get("1世帯あたり人員"):
            lines.append("  1世帯あたり {}人".format(item["1世帯あたり人員"]["value"]))
        if item["高齢化率"]:
            lines.append("  高齢化率 {}%／年少人口 {}%".format(
                item["高齢化率"]["percent"],
                (item["年少人口比率"] or {}).get("percent", "—")))
        if item.get("社会増減"):
            lines.append("  転入 {} − 転出 {} ＝ {}（{}年）".format(
                _fmt(item["転入者数"]["value"]), _fmt(item["転出者数"]["value"]),
                _fmt(item["社会増減"]["value"], "人"), item["社会増減"]["year"]))
        if item.get("2040年の人口増減率"):
            lines.append("  2040年推計 {}（{}%）".format(
                _fmt(item["将来推計人口2040"]["value"], "人"),
                item["2040年の人口増減率"]["percent"]))

    return {
        "ok": True,
        "source": "e-Stat 社会・人口統計体系 市区町村データ（国勢調査・住民基本台帳ほか）",
        "areas": out,
        "formatted": "\n".join(lines),
        "note": "市区町村単位の値。町丁目・駅徒歩圏の粒度は無い。回答には必ず調査年を添えること",
    }


def estat_housing_profile(property=None, address=None, city=None, city_code=None, compare=None):
    """商圏の住宅・空き家・借家（e-Stat 住宅土地統計調査ほか）。compare で市区町村を比較できる。"""
    try:
        estat = _import()
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    targets = []
    code, label, err = _resolve_area(estat, city_code, property, address, city)
    if err:
        return {"ok": False, "error": err}
    targets.append((code, label))
    for other in (compare or []):
        other = str(other).strip()
        if not other:
            continue
        if other.isdigit():
            c, l, e2 = _resolve_area(estat, city_code=other)
        else:
            c, l, e2 = _resolve_area(estat, city=other)
        if e2:
            return {"ok": False, "error": e2}
        targets.append((c, l))

    try:
        rows = _collect(estat, "housing", targets, _HOUSING_CATS)
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    out = []
    lines = []
    for row in rows:
        v = row["values"]
        item = {
            "city_code": row["city_code"],
            "city": row["city"],
            "asked_as": row["asked_as"],
            "総住宅数": _pick(v, "H1100"),
            "居住世帯あり住宅数": _pick(v, "H1101"),
            "空き家数": _pick(v, "H110202"),
            "持ち家数": _pick(v, "H1310"),
            "借家数": _pick(v, "H1320"),
            "民営借家数": _pick(v, "H1322"),
            "共同住宅数": _pick(v, "H1403"),
            "着工新設貸家数": _pick(v, "H1802"),
            "1住宅あたり延べ面積": _pick(v, "H2130"),
            "1住宅あたり延べ面積_借家": _pick(v, "H213020"),
            "空き家率": _ratio(v, "H110202", "H1100"),
            "借家率": _ratio(v, "H1320", "H1101"),
            "民営借家の割合": _ratio(v, "H1322", "H1320"),
            "共同住宅率": _ratio(v, "H1403", "H1100"),
            "持ち家率": _ratio(v, "H1310", "H1101"),
        }
        out.append(item)

        lines.append("■ {}".format(item["city"]))
        if item["総住宅数"]:
            lines.append("  総住宅 {}（{}年）／空き家 {}（空き家率 {}%）".format(
                _fmt(item["総住宅数"]["value"], "戸"), item["総住宅数"]["year"],
                _fmt((item["空き家数"] or {}).get("value"), "戸"),
                (item["空き家率"] or {}).get("percent", "—")))
        if item["借家率"]:
            lines.append("  借家 {}（借家率 {}%・うち民営 {}%）".format(
                _fmt((item["借家数"] or {}).get("value"), "戸"),
                item["借家率"]["percent"],
                (item["民営借家の割合"] or {}).get("percent", "—")))
        if item["共同住宅率"]:
            lines.append("  共同住宅 {}（{}%）".format(
                _fmt((item["共同住宅数"] or {}).get("value"), "戸"),
                item["共同住宅率"]["percent"]))
        if item["着工新設貸家数"]:
            lines.append("  着工新設貸家 {}（{}年・新規供給の勢い）".format(
                _fmt(item["着工新設貸家数"]["value"], "戸"), item["着工新設貸家数"]["year"]))
        if item["1住宅あたり延べ面積_借家"]:
            lines.append("  借家1戸あたり {}㎡".format(item["1住宅あたり延べ面積_借家"]["value"]))

    return {
        "ok": True,
        "source": "e-Stat 社会・人口統計体系 市区町村データ（住宅・土地統計調査／建築着工統計）",
        "areas": out,
        "formatted": "\n".join(lines),
        "note": "空き家数には賃貸募集中の空室も含まれる（＝管理物件の空室率とは別物）。"
                "回答には必ず調査年を添えること",
    }


def estat_indicator_search(keyword, table=None, limit=40):
    """e-Stat の項目をキーワードで探す（既定は人口・世帯＋居住の2表）。"""
    try:
        estat = _import()
        items = estat.search_indicators(keyword, table=table, limit=int(limit))
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}
    return {
        "ok": True, "keyword": keyword, "count": len(items), "indicators": items,
        "hint": "見つかったコードは estat_indicator_value の codes に渡す",
    }


def estat_indicator_value(codes, table="population", property=None, address=None,
                          city=None, city_code=None, compare=None, history=False):
    """estat_indicator_search で見つけた任意の項目を取る（複数市区町村・時系列も可）。"""
    try:
        estat = _import()
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    if isinstance(codes, str):
        codes = [c.strip() for c in codes.split(",") if c.strip()]

    targets = []
    code, label, err = _resolve_area(estat, city_code, property, address, city)
    if err:
        return {"ok": False, "error": err}
    targets.append((code, label))
    for other in (compare or []):
        other = str(other).strip()
        if not other:
            continue
        if other.isdigit():
            c, l, e2 = _resolve_area(estat, city_code=other)
        else:
            c, l, e2 = _resolve_area(estat, city=other)
        if e2:
            return {"ok": False, "error": e2}
        targets.append((c, l))

    try:
        data = estat.get_values(table, [t[0] for t in targets], codes,
                                latest_only=not history)
    except Exception as e:
        return {"ok": False, "error": "{}: {}".format(type(e).__name__, e)}

    areas = []
    for c, label in targets:
        area = data["areas"].get(c, {})
        areas.append({"city_code": c, "city": area.get("name") or label,
                      "values": area.get("values", {})})
    return {"ok": True, "table": data["table_label"], "areas": areas,
            "source": "e-Stat 社会・人口統計体系 市区町村データ"}
