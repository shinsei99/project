"""日本郵便「郵便番号・デジタルアドレスAPI」ツール（住所と郵便番号の突き合わせ）。

- zip_lookup:      郵便番号・事業所個別郵便番号・デジタルアドレス → 住所
- address_to_zip:  住所の一部 → 郵便番号（送付書・宛名・重説の住所欄の裏取りに使う）

実体は**直下の共有クライアント `japanpost_api.py`**（他アプリと同じ1本。コピーを作らない）。
資格情報は直下 `.env.japanpost`（本番・gitignore）。トークンは自動更新されるので呼ぶ側は意識しない。

社内資料（kb_search）に載っている住所は人が入力したもので誤りが混ざる。**公式の郵便番号データと
照合できる**のがこのToolの値打ちで、「この住所で合っていますか」に根拠つきで答えられる。

はまり所（2026-08-21 実測）:
  - `addresszip` は**番地まで入れると 404**。「大阪市都島区東野田町2-3-1」は見つからず、
    番地を落とした「大阪市都島区東野田町」なら引ける。→ 段階的に末尾を削って引き直している
  - 郵便番号は3桁以上で引ける（7桁未満は前方一致）
"""
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

_KEYS = ("zip_code", "dgacode", "pref_name", "city_name", "town_name",
         "block_name", "other_name", "pref_kana", "city_kana", "town_kana")


def _import():
    import japanpost_api  # 直下の共有クライアント
    return japanpost_api


def _addr(a):
    """返りから必要な項目だけ拾い、1行の住所も組み立てる。"""
    out = {k: a.get(k) for k in _KEYS if a.get(k)}
    out["address"] = "".join(
        str(a.get(k) or "") for k in ("pref_name", "city_name", "town_name", "block_name")
    )
    return out


def zip_lookup(code, limit=10):
    """郵便番号（3桁以上）・事業所個別郵便番号・デジタルアドレスから住所を引く。

    code: "5340024" / "534" のような郵便番号、または "A7G2-B8" 形式のデジタルアドレス。
    """
    code = str(code or "").strip().replace("-", "").replace("ー", "")
    if not code:
        return {"ok": False, "error": "郵便番号（またはデジタルアドレス）を渡してください"}
    try:
        data = _import().search_code(code, limit=int(limit))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    addrs = [_addr(a) for a in (data.get("addresses") or [])][: int(limit)]
    return {
        "ok": True,
        "code": code,
        "searchtype": data.get("searchtype"),
        "count": data.get("count"),
        "addresses": addrs,
        "source": "日本郵便 郵便番号・デジタルアドレスAPI",
    }


def address_to_zip(address=None, pref_name=None, city_name=None, town_name=None, limit=10):
    """住所（の一部）から郵便番号を引く。

    address に丸ごと渡してもよいし、pref_name / city_name / town_name に分けて渡してもよい。
    戻りの level は 1=都道府県まで一致 / 2=市区町村まで / 3=町域まで。
    """
    jp = _import()
    if any([pref_name, city_name, town_name]):
        params = {k: v for k, v in
                  (("pref_name", pref_name), ("city_name", city_name), ("town_name", town_name))
                  if v}
        try:
            data = jp.address_zip(limit=int(limit), **params)
        except Exception as e:
            return {"ok": False, "error": f"{type(e).__name__}: {e}", "query": params}
        return {"ok": True, "query": params, "level": data.get("level"),
                "count": data.get("count"),
                "addresses": [_addr(a) for a in (data.get("addresses") or [])][: int(limit)],
                "source": "日本郵便 郵便番号・デジタルアドレスAPI"}

    if not address:
        return {"ok": False, "error": "address か pref_name/city_name/town_name のどれかが要ります"}

    tried, last = [], None
    for cand in jp._address_candidates(address):  # 番地落としは共有クライアント側に1本だけ置く
        if cand in tried:
            continue
        tried.append(cand)
        try:
            data = jp.address_zip(freeword=cand, limit=int(limit))
        except Exception as e:
            last = f"{type(e).__name__}: {e}"
            continue
        return {
            "ok": True,
            "input": address,
            "matched_by": cand,
            "note": ("番地を落として引き直しました（APIは番地まで入れると見つからない）"
                     if cand != address else None),
            "level": data.get("level"),
            "count": data.get("count"),
            "addresses": [_addr(a) for a in (data.get("addresses") or [])][: int(limit)],
            "source": "日本郵便 郵便番号・デジタルアドレスAPI",
        }
    return {"ok": False, "error": last or "該当する住所が見つかりませんでした",
            "input": address, "tried": tried}
