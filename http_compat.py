#!/usr/bin/env python3
"""`requests` が無い環境でも動くための最小互換層 — 直下の共有モジュール（2026-08-23 作成）。

## なぜ要るか

直下の API クライアント（`japanpost_api` / `egov_law_api` / `google_maps_api` /
`appstore_api`）は Streamlit アプリからも、**AI業務マネージャーの常駐 worker からも**呼ばれる。
worker は launchd から **`/usr/bin/python3`**（macOS 同梱の素の Python）で動いていて、
`chatwork-ai-manager/requirements.txt` は「HTTP は urllib を使うので requests 等は不要」と
明言している。つまり **requests が入っている保証が無い**。

requests 前提のまま Tool を足すと、**本番で ImportError になって初めて気づく**。
実際 2026-08-23 に、法令Tool（e-Gov）と郵便番号Tool（日本郵便）がその状態だった。

## 使い方

    import http_compat
    requests = http_compat.get_requests()   # 本物の requests か、無ければ urllib のシム

以降は `requests.get(...)` / `requests.post(...)` / `requests.Session()` /
`requests.exceptions.RequestException` を今までどおり書ける。

## シムが真似る範囲（クライアント4本が実際に使っている分だけ）

- `get(url, params=…, headers=…, timeout=…)` / `post(url, headers=…, json=…, timeout=…)`
- 戻り値の `status_code` / `text` / `content` / `json()` / `raise_for_status()`
- `Session()`（接続の使い回しはしない。**インターフェースだけ合わせる**）
- `exceptions.RequestException` / `exceptions.HTTPError`

**4xx/5xx は例外にせず戻り値で返す**（requests と同じ挙動）。`raise_for_status()` で初めて上げる。
これ以上は増やさないこと。増やしたくなったら requests を入れる方が正しい。
"""

from __future__ import annotations

import json as _json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

USER_AGENT = "daikyo-api-client/1.0"
DEFAULT_TIMEOUT = 30


class _Exceptions:
    class RequestException(Exception):
        """通信そのものの失敗（DNS・接続断・タイムアウト）。"""

    HTTPError = RequestException
    ConnectionError = RequestException
    Timeout = RequestException


class _Response:
    """requests の Response のうち、直下のクライアントが使う分だけ。"""

    def __init__(self, status_code: int, body: bytes, url: str = ""):
        self.status_code = status_code
        self.content = body
        self.url = url

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", "replace")

    def json(self) -> Any:
        return _json.loads(self.content.decode("utf-8"))

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise _Exceptions.HTTPError(
                "HTTP {} for {}".format(self.status_code, self.url))


class _UrllibRequests:
    """urllib で requests の入口だけを真似る。"""

    exceptions = _Exceptions

    @staticmethod
    def _send(url: str, params=None, headers=None, data: Optional[bytes] = None,
              method: str = "GET", timeout: int = DEFAULT_TIMEOUT) -> _Response:
        if params:
            sep = "&" if "?" in url else "?"
            url = url + sep + urllib.parse.urlencode(params)
        head: Dict[str, str] = {"User-Agent": USER_AGENT}
        head.update(headers or {})
        req = urllib.request.Request(url, data=data, headers=head, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return _Response(resp.status, resp.read(), url)
        except urllib.error.HTTPError as e:
            # 4xx/5xx は requests と同じく「戻り値」で返す（例外にしない）
            return _Response(e.code, e.read(), url)
        except Exception as e:  # DNS・接続断・タイムアウト
            raise _Exceptions.RequestException(str(e)) from e

    @classmethod
    def get(cls, url, params=None, headers=None, timeout=DEFAULT_TIMEOUT, **_):
        return cls._send(url, params=params, headers=headers, timeout=timeout)

    @classmethod
    def post(cls, url, params=None, headers=None, json=None, data=None,
             timeout=DEFAULT_TIMEOUT, **_):
        head = dict(headers or {})
        body = data
        if json is not None:
            body = _json.dumps(json).encode("utf-8")
            head.setdefault("Content-Type", "application/json")
        elif isinstance(data, dict):
            body = urllib.parse.urlencode(data).encode("utf-8")
            head.setdefault("Content-Type", "application/x-www-form-urlencoded")
        return cls._send(url, params=params, headers=head, data=body,
                         method="POST", timeout=timeout)

    @classmethod
    def Session(cls):  # noqa: N802 - requests に合わせる
        return cls()


def get_requests():
    """本物の `requests`。無ければ urllib のシムを返す。"""
    try:
        import requests  # type: ignore
        return requests
    except ImportError:
        return _UrllibRequests()


def using_shim() -> bool:
    """いま urllib のシムで動いているか（ログや診断用）。"""
    return not hasattr(get_requests(), "__version__")


if __name__ == "__main__":
    r = get_requests()
    print("requests:", "本物" if not using_shim() else "urllib シム")
    resp = r.get("https://api.ipify.org", params={"format": "json"}, timeout=10)
    print("疎通:", resp.status_code, resp.json())
