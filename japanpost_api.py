#!/usr/bin/env python3
"""日本郵便「郵便番号・デジタルアドレスAPI」の共通クライアント（2026-08-19 作成）。

複数アプリ（soufu-maker / kaitori-dm-maker / tsuikyaku-crm など）から住所の正規化に使うため、
**直下に1本だけ置く**。アプリ側からは次のどちらかで読む:

    import sys, pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
    import japanpost_api

資格情報は **`.env.japanpost`（直下・gitignore・600）** に置く。値をコードに書かない。

    JAPANPOST_CLIENT_ID=...
    JAPANPOST_SECRET_KEY=...
    JAPANPOST_SOURCE_IP=...      # 任意。省略時は起動時に自動判定して .japanpost-token.json に控える

APIの仕様（2026-08-19 時点・API Reference 1.0.2.260209 より）:

  POST /api/v2/j/token            OAuth2 client_credentials。**ヘッダ x-forwarded-for が必須**。
                                  返りは JWT（token / token_type / expires_in / scope）
  GET  /api/v2/searchcode/{code}  郵便番号・事業所個別郵便番号・デジタルアドレスの統一検索
  POST /api/v2/addresszip         住所の一部 → 郵便番号・住所（level 1=都道府県 2=市区町村 3=町域）

確かめたこと（2026-08-19・テスト用stubに対して実測）:
  - x-forwarded-for は**自分のグローバルIPを入れれば通る**（api.ipify.org で自動判定している）
  - searchcode "100" → 千代田区 内幸町/大手町 の2件。addresszip 13/13101 → level=2 で6件
  - **テスト用の資格情報は本番ホストでは 401**（stub と本番は資格情報ごと別）

**未確認**: レート制限の具体的な数値（公開情報は「一定時間内のリクエスト数に制限」のみ）
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import re
import time
import urllib.parse
from typing import Any

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import http_compat  # requests が無い環境（launchd の /usr/bin/python3）でも動かすための互換層

requests = http_compat.get_requests()

# 本番ホスト。テスト用（stub）に切り替えるときは .env.japanpost に JAPANPOST_HOST を書く。
# 例: JAPANPOST_HOST=stub-qz73x.da.pf.japanpost.jp
DEFAULT_HOST = "api.da.pf.japanpost.jp"
ROOT = pathlib.Path(__file__).resolve().parent
ENV_FILE = ROOT / ".env.japanpost"
TOKEN_CACHE = ROOT / ".japanpost-token.json"
TIMEOUT = 15
# 期限ぎりぎりで使って 401 になるのを避けるための余裕（秒）
EXPIRY_MARGIN = 60


class JapanPostError(RuntimeError):
    pass


def base_url() -> str:
    """接続先。テスト用に向けているかどうかは、この関数の返り値で分かる。"""
    host = _load_env().get("JAPANPOST_HOST") or DEFAULT_HOST
    return f"https://{host}"


def _load_env() -> dict[str, str]:
    """.env.japanpost を読む。環境変数が既にあればそちらを優先する。"""
    env: dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    for k in ("JAPANPOST_CLIENT_ID", "JAPANPOST_SECRET_KEY", "JAPANPOST_SOURCE_IP", "JAPANPOST_HOST"):
        if os.environ.get(k):
            env[k] = os.environ[k]
    return env


def _source_ip(env: dict[str, str]) -> str:
    """x-forwarded-for に入れる送信元IP。指定が無ければ一度だけ調べて控える。"""
    if env.get("JAPANPOST_SOURCE_IP"):
        return env["JAPANPOST_SOURCE_IP"]
    cached = _read_cache()
    if cached.get("source_ip"):
        return cached["source_ip"]
    try:
        ip = requests.get("https://api.ipify.org", timeout=TIMEOUT).text.strip()
    except Exception as e:
        raise JapanPostError(
            "送信元IPを判定できませんでした。.env.japanpost に JAPANPOST_SOURCE_IP を書いてください"
        ) from e
    _write_cache({**cached, "source_ip": ip})
    return ip


def _read_cache() -> dict[str, Any]:
    if not TOKEN_CACHE.exists():
        return {}
    try:
        return json.loads(TOKEN_CACHE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _write_cache(data: dict[str, Any]) -> None:
    TOKEN_CACHE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    TOKEN_CACHE.chmod(0o600)


def get_token(force: bool = False) -> str:
    """API利用トークン（JWT）を返す。expires_in の間はファイルに控えて使い回す。

    トークンを取り直すたびに1コール消費するので、**毎回取らない**こと。
    """
    cache = _read_cache()
    # 接続先が変わったらトークンを取り直す（stub のトークンで本番を叩かないため）
    if cache.get("host") != base_url():
        cache = {k: v for k, v in cache.items() if k == "source_ip"}
    if not force and cache.get("token") and cache.get("expires_at", 0) > time.time() + EXPIRY_MARGIN:
        return cache["token"]

    env = _load_env()
    cid, sec = env.get("JAPANPOST_CLIENT_ID"), env.get("JAPANPOST_SECRET_KEY")
    if not cid or not sec:
        raise JapanPostError(
            f"{ENV_FILE.name} に JAPANPOST_CLIENT_ID / JAPANPOST_SECRET_KEY がありません"
        )

    try:
        resp = requests.post(
            f"{base_url()}/api/v2/j/token",
            headers={"Content-Type": "application/json", "x-forwarded-for": _source_ip(env)},
            json={"grant_type": "client_credentials", "client_id": cid, "secret_key": sec},
            timeout=TIMEOUT,
        )
    except Exception as e:
        raise JapanPostError(f"トークンの取得に失敗しました: {e}") from e

    if resp.status_code != 200:
        raise JapanPostError(f"トークンの取得に失敗しました (HTTP {resp.status_code}): {resp.text[:200]}")

    body = resp.json()
    token = body.get("token")
    if not token:
        raise JapanPostError(f"トークンが返りませんでした: {body}")
    _write_cache(
        {
            **cache,
            "host": base_url(),
            "token": token,
            "expires_at": time.time() + float(body.get("expires_in", 0) or 0),
            "scope": body.get("scope"),
        }
    )
    return token


def _auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {get_token()}", "Content-Type": "application/json"}


def search_code(
    code: str,
    *,
    page: int = 1,
    limit: int = 1000,
    choikitype: int = 1,
    searchtype: int = 1,
) -> dict[str, Any]:
    """郵便番号・事業所個別郵便番号・デジタルアドレスの統一検索。

    郵便番号は3桁以上。7桁未満なら「その値で始まるもの」のパターン検索になる。
    choikitype 1=括弧なし町域 / 2=括弧あり。searchtype 2 は事業所個別郵便番号を除く。
    """
    q = urllib.parse.urlencode(
        {"page": page, "limit": limit, "choikitype": choikitype, "searchtype": searchtype}
    )
    url = f"{base_url()}/api/v2/searchcode/{urllib.parse.quote(str(code))}?{q}"
    resp = requests.get(url, headers=_auth_headers(), timeout=TIMEOUT)
    if resp.status_code != 200:
        raise JapanPostError(f"検索に失敗しました (HTTP {resp.status_code}): {resp.text[:200]}")
    return resp.json()


def address_zip(**params: Any) -> dict[str, Any]:
    """住所の一部から郵便番号・住所を引く。

    使える主なキー: pref_code / pref_name / city_code / city_name / town_name /
    freeword / flg_getpref / flg_getcity / page / limit。
    **コードと名称を両方渡した場合はコードが優先される**（pref_code > pref_name など）。
    返りの level は 1=都道府県一致 / 2=市区町村一致 / 3=町域一致。
    """
    resp = requests.post(
        f"{base_url()}/api/v2/addresszip", headers=_auth_headers(), json=params, timeout=TIMEOUT
    )
    if resp.status_code != 200:
        raise JapanPostError(f"住所検索に失敗しました (HTTP {resp.status_code}): {resp.text[:200]}")
    return resp.json()



# ─────────────────────────────────────────────────────────────────────────
# 住所の照合（2026-08-23 追加）
#
# 台帳・謄本の住所は**人が入力したもの**で、郵便番号の抜けや旧町名・誤字が混ざる。
# DM や送付書はそのまま印字すると**不達・返送**になり、1通ずつ郵送費が無駄になる。
# 「公式データと突き合わせる」だけの薄い関数をここに置き、各アプリから同じものを呼ぶ。
# （chatwork-ai-manager の zip_lookup / address_to_zip もここへ寄せている）
# ─────────────────────────────────────────────────────────────────────────

_ZEN2HAN = str.maketrans("０１２３４５６７８９－―ー‐　", "0123456789---- ")


def normalize_jp(text: Any) -> str:
    """比較用に住所を正規化する（全角→半角・記号とスペースの揺れを吸収）。"""
    t = str(text or "").translate(_ZEN2HAN)
    t = t.replace("ヶ", "ケ").replace("之", "ノ")
    return re.sub(r"[\s\-]", "", t)


def zip_digits(code: Any) -> str:
    """郵便番号を数字だけにする（"〒534-0024" → "5340024"）。"""
    return re.sub(r"\D", "", str(code or ""))


def _address_candidates(address: str):
    """番地つきの住所から、APIに通る形へ段階的に短くした候補を作る。

    `addresszip` は**番地まで入れると 404**（2026-08-21 実測）。町域までなら引ける。
    """
    a = str(address or "").strip()
    if not a:
        return
    yield a
    cut = re.split(r"[0-9０-９]+[-－ー‐]|[0-9０-９]+丁目|[0-9０-９]+番", a)[0]
    if cut and cut != a:
        yield cut.rstrip("　 ")
    tail = re.sub(r"[0-9０-９\-－ー‐番地号丁目\s]+$", "", a)
    if tail and tail not in (a, cut):
        yield tail


def _join_address(a: dict[str, Any], with_pref: bool = True) -> str:
    keys = ("pref_name", "city_name", "town_name") if with_pref else ("city_name", "town_name")
    return "".join(str(a.get(k) or "") for k in keys)


def address_for_zip(code: Any, limit: int = 10) -> dict[str, Any]:
    """郵便番号（3桁以上）・デジタルアドレス → 住所。失敗しても例外にしない。"""
    code = zip_digits(code) or str(code or "").strip()
    if not code:
        return {"ok": False, "error": "郵便番号がありません"}
    try:
        data = search_code(code, limit=int(limit))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    addrs = data.get("addresses") or []
    return {
        "ok": bool(addrs), "code": code, "count": data.get("count"),
        "addresses": addrs,
        "address": _join_address(addrs[0]) if addrs else "",
        "error": "" if addrs else "この郵便番号は見つかりませんでした",
    }


def zip_for_address(address: str, limit: int = 10) -> dict[str, Any]:
    """住所 → 郵便番号。番地は自動で落として引き直す。

    戻り値の `level` は 1=都道府県まで / 2=市区町村まで / **3=町域まで一致**。
    3 以外は「候補どまり」で、そのまま宛名には使わないこと。
    """
    tried, last_error = [], ""
    for cand in _address_candidates(address):
        if cand in tried:
            continue
        tried.append(cand)
        try:
            data = address_zip(freeword=cand, limit=int(limit))
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            continue
        addrs = data.get("addresses") or []
        if addrs:
            return {
                "ok": True, "query": cand, "tried": tried,
                "level": data.get("level"), "count": data.get("count"),
                "zip_code": str(addrs[0].get("zip_code") or ""),
                "address": _join_address(addrs[0]),
                "addresses": addrs[: int(limit)],
            }
    return {"ok": False, "tried": tried,
            "error": last_error or "住所から郵便番号を特定できませんでした"}


def verify(postal: Any = None, address: str = "") -> dict[str, Any]:
    """郵便番号と住所の突き合わせ。**判定と、そのまま画面に出せる一言**を返す。

    status は次のどれか:
      "一致"        … 郵便番号の公式住所が、入力住所の頭と一致した
      "不一致"      … 郵便番号は実在するが、住所が別の地域を指している（要確認）
      "補完"        … 郵便番号が空欄で、住所から町域まで特定できた（`zip_code` を使える）
      "候補"        … 住所から市区町村までしか絞れなかった（人が確かめる）
      "不明"        … 郵便番号が存在しない・住所も特定できない
      "住所なし"    … 住所が空（郵便番号だけ検証した）
    """
    postal = zip_digits(postal)
    address = str(address or "").strip()

    if postal:
        found = address_for_zip(postal)
        if not found.get("ok"):
            return {"status": "不明", "zip_code": postal, "official": "",
                    "message": f"郵便番号 {postal} は見つかりませんでした",
                    "detail": found.get("error", "")}
        if not address:
            return {"status": "住所なし", "zip_code": postal,
                    "official": found["address"],
                    "message": f"住所が空欄です（{postal} は {found['address']}）"}
        target = normalize_jp(address)
        for a in found["addresses"]:
            for with_pref in (True, False):
                official = normalize_jp(_join_address(a, with_pref))
                if official and target.startswith(official):
                    return {"status": "一致", "zip_code": postal,
                            "official": _join_address(a),
                            "message": "郵便番号と住所が一致"}
        return {"status": "不一致", "zip_code": postal, "official": found["address"],
                "message": f"〒{postal} は「{found['address']}」です（入力: {address}）"}

    if not address:
        return {"status": "不明", "zip_code": "", "official": "",
                "message": "郵便番号も住所もありません"}

    guess = zip_for_address(address)
    if not guess.get("ok"):
        return {"status": "不明", "zip_code": "", "official": "",
                "message": "住所から郵便番号を特定できませんでした",
                "detail": guess.get("error", "")}
    if str(guess.get("level")) == "3":
        return {"status": "補完", "zip_code": guess["zip_code"],
                "official": guess["address"],
                "message": f"郵便番号を補完しました（{guess['zip_code']} {guess['address']}）"}
    return {"status": "候補", "zip_code": guess["zip_code"], "official": guess["address"],
            "message": f"市区町村までしか絞れません（候補 {guess['zip_code']} {guess['address']}）"}


if __name__ == "__main__":
    import sys

    code = sys.argv[1] if len(sys.argv) > 1 else "5410053"
    print(f"郵便番号 {code} を引きます（{base_url()}）")
    try:
        got = search_code(code, limit=5)
    except JapanPostError as e:
        print(f"NG: {e}")
        sys.exit(1)
    print(f"count={got.get('count')} searchtype={got.get('searchtype')}")
    for a in (got.get("addresses") or [])[:5]:
        print("  ", {k: v for k, v in a.items() if v})
