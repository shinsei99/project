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
import time
import urllib.parse
from typing import Any

import requests

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
