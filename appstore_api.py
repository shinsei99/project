#!/usr/bin/env python3
"""App Store Connect API の共通クライアント（2026-08-20 作成）。

**目的**: 「App Store に実際に登録済みのビルド番号」を照会し、再アップロードの衝突を
機械的に防ぐ（2026-07-22に、build番号を上げずに再アーカイブして**修正前のビルドが
審査を通り配信された**事故があったため）。`./ios-build-guard.sh` から呼ばれる。

**キーはチーム単位＝1本作れば全アプリに効く**（アプリごとの発行は不要）。

設定は **`.env.appstore`（直下・gitignore・600）**:

    ASC_KEY_ID=XXXXXXXXXX               # キーID
    ASC_ISSUER_ID=xxxxxxxx-xxxx-....    # Issuer ID（チームで共通）
    ASC_PRIVATE_KEY_PATH=/Users/apple/.appstore/AuthKey_XXXXXXXXXX.p8

`.p8` は **App Store Connect からダウンロードできるのは1回だけ**。無くしたら再発行になる。

認証は JWT（ES256）。PyJWT は入れず、`cryptography` だけで署名している
（DER 形式の署名を R‖S の64バイトに直す必要がある。ここが唯一のはまりどころ）。
トークンの有効期限は **最大20分**（Apple の制限）。

※ チームキー前提（`iss` に Issuer ID を入れる）。個人キー（Individual Key）は
  `iss` ではなく `sub` を使う仕様なので、そのときは払い出し方を変えること（**未確認**）。

**審査状況の照会もできる**（2026-08-23 追加）: `python3 appstore_api.py --review`。
審査は App Store Connect の画面を見に行かなくても、ここから状態が取れる。
"""

from __future__ import annotations

import base64
import json
import pathlib
import sys
import time
from typing import Any, Dict, List, Optional

_HERE = pathlib.Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import http_compat  # requests が無い環境（launchd の /usr/bin/python3）でも動かすための互換層

requests = http_compat.get_requests()

BASE = "https://api.appstoreconnect.apple.com/v1"
ENV_PATH = pathlib.Path(__file__).resolve().parent / ".env.appstore"
TOKEN_TTL = 900  # 15分（上限20分より短くしておく）
TIMEOUT = 30
RETRY = 3

# 接続を毎回張り直すと Apple 側で TLS が切れる（SSLEOFError）。セッションを使い回す。
_SESSION = requests.Session()
_TOKEN_CACHE: Dict[str, Any] = {"value": "", "exp": 0.0}


class AppStoreError(RuntimeError):
    """設定不足・API エラー。"""


def _load_env() -> Dict[str, str]:
    import os

    env: Dict[str, str] = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("ASC_KEY_ID", "ASC_ISSUER_ID", "ASC_PRIVATE_KEY_PATH"):
        if os.environ.get(k):
            env[k] = os.environ[k].strip()
    return env


def is_configured() -> bool:
    """呼び出し側が「APIを使えるか」を静かに判定するため。"""
    env = _load_env()
    if not (env.get("ASC_KEY_ID") and env.get("ASC_ISSUER_ID") and env.get("ASC_PRIVATE_KEY_PATH")):
        return False
    return pathlib.Path(env["ASC_PRIVATE_KEY_PATH"]).expanduser().exists()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def token() -> str:
    """App Store Connect API 用の JWT を作る（ES256・15分）。有効なうちは作り直さない。"""
    if _TOKEN_CACHE["value"] and time.time() < _TOKEN_CACHE["exp"] - 60:
        return str(_TOKEN_CACHE["value"])
    env = _load_env()
    key_id = env.get("ASC_KEY_ID", "")
    issuer = env.get("ASC_ISSUER_ID", "")
    key_path = env.get("ASC_PRIVATE_KEY_PATH", "")
    if not (key_id and issuer and key_path):
        raise AppStoreError(
            ".env.appstore に ASC_KEY_ID / ASC_ISSUER_ID / ASC_PRIVATE_KEY_PATH が要ります。"
        )
    path = pathlib.Path(key_path).expanduser()
    if not path.exists():
        raise AppStoreError("秘密鍵(.p8)が見つかりません: {}".format(path))

    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec, utils as asym_utils

    private_key = serialization.load_pem_private_key(path.read_bytes(), password=None)

    now = int(time.time())
    header = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    payload = {"iss": issuer, "iat": now, "exp": now + TOKEN_TTL, "aud": "appstoreconnect-v1"}
    signing_input = "{}.{}".format(
        _b64(json.dumps(header, separators=(",", ":")).encode()),
        _b64(json.dumps(payload, separators=(",", ":")).encode()),
    ).encode()

    der = private_key.sign(signing_input, ec.ECDSA(hashes.SHA256()))
    r, s = asym_utils.decode_dss_signature(der)
    raw = r.to_bytes(32, "big") + s.to_bytes(32, "big")  # JWS は DER ではなく R‖S
    jwt_value = "{}.{}".format(signing_input.decode(), _b64(raw))
    _TOKEN_CACHE["value"] = jwt_value
    _TOKEN_CACHE["exp"] = now + TOKEN_TTL
    return jwt_value


def _get(path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    last: Optional[Exception] = None
    for attempt in range(RETRY):
        try:
            resp = _SESSION.get(
                "{}{}".format(BASE, path),
                headers={"Authorization": "Bearer {}".format(token())},
                params=params or {},
                timeout=TIMEOUT,
            )
            break
        except requests.exceptions.RequestException as e:
            last = e  # SSLEOFError など。少し待って張り直す
            time.sleep(0.5 * (attempt + 1))
    else:
        raise AppStoreError("通信に失敗しました（{}回試行）: {}".format(RETRY, last))
    if resp.status_code == 401:
        raise AppStoreError("認証に失敗しました（キーID・Issuer ID・.p8 の対応を確認）")
    if resp.status_code == 403:
        raise AppStoreError("権限が足りません（キーの役割を上げる必要があります）: {}".format(resp.text[:200]))
    if resp.status_code != 200:
        raise AppStoreError("APIエラー (HTTP {}): {}".format(resp.status_code, resp.text[:200]))
    return resp.json()


def list_apps() -> List[Dict[str, str]]:
    """登録済みアプリの一覧。{"id", "bundleId", "name"} の配列。"""
    data = _get("/apps", {"limit": 200})
    return [
        {
            "id": a.get("id", ""),
            "bundleId": a.get("attributes", {}).get("bundleId", ""),
            "name": a.get("attributes", {}).get("name", ""),
        }
        for a in data.get("data", [])
    ]


def app_id(bundle_id: str) -> Optional[str]:
    """Bundle ID から App Store 上のアプリIDを引く。"""
    data = _get("/apps", {"filter[bundleId]": bundle_id, "limit": 1})
    items = data.get("data", [])
    return items[0].get("id") if items else None


def builds(bundle_id: str, limit: int = 200, aid: Optional[str] = None) -> List[Dict[str, str]]:
    """そのアプリの登録済みビルド。{"version"(=build番号), "uploadedDate", "state"}。

    `aid`（アプリID）を渡すと Bundle ID からの検索を省ける（通信1回ぶん減る）。
    """
    aid = aid or app_id(bundle_id)
    if not aid:
        return []
    data = _get("/builds", {"filter[app]": aid, "limit": limit})
    out = []
    for b in data.get("data", []):
        attr = b.get("attributes", {})
        out.append({
            "version": str(attr.get("version", "")),
            "uploadedDate": str(attr.get("uploadedDate", "")),
            "state": str(attr.get("processingState", "")),
        })
    return out


# 審査・配信の状態（appStoreVersions の state）。値は Apple の定義そのまま。
# よく出るものだけ日本語を添える（未知の値はそのまま英語で出す）。
REVIEW_STATE_JA = {
    "PREPARE_FOR_SUBMISSION": "提出準備中（まだ出していない）",
    "WAITING_FOR_REVIEW": "審査待ち",
    "IN_REVIEW": "審査中",
    "PENDING_DEVELOPER_RELEASE": "審査通過・こちらのリリース操作待ち",
    "PENDING_APPLE_RELEASE": "審査通過・Apple のリリース待ち",
    "PROCESSING_FOR_APP_STORE": "配信処理中",
    "READY_FOR_SALE": "配信中",
    "READY_FOR_DISTRIBUTION": "配信中",
    "REJECTED": "リジェクト（要対応）",
    "METADATA_REJECTED": "メタデータのリジェクト（要対応）",
    "DEVELOPER_REJECTED": "こちらが取り下げた",
    "DEVELOPER_REMOVED_FROM_SALE": "販売停止中",
    "INVALID_BINARY": "バイナリが無効（要再アップ）",
    "REPLACED_WITH_NEW_VERSION": "新しいバージョンに置き換わった",
}


def versions(bundle_id: str, limit: int = 10, aid: Optional[str] = None) -> List[Dict[str, str]]:
    """App Store 上のバージョンと**審査の状態**。新しい順。

    各要素: {"version"(表示バージョン), "state", "state_ja", "platform",
             "created"(作成日), "released"(配信日・無ければ空)}。
    ビルド番号ではなく `MARKETING_VERSION` の話なので `builds()` とは別物。
    """
    aid = aid or app_id(bundle_id)
    if not aid:
        return []
    # ★ `/appStoreVersions?filter[app]=…` は **403**（GET_COLLECTION が許されていない）。
    #   アプリ配下の関係エンドポイントなら通る（2026-08-23 実測）
    data = _get("/apps/{}/appStoreVersions".format(aid), {"limit": limit})
    out = []
    for v in data.get("data", []):
        attr = v.get("attributes", {})
        # 州によってキー名が違う時期があったので両方見る（appStoreState は旧・state は新）
        state = str(attr.get("appStoreState") or attr.get("state") or "")
        out.append({
            "version": str(attr.get("versionString", "")),
            "state": state,
            "state_ja": REVIEW_STATE_JA.get(state, state),
            "platform": str(attr.get("platform", "")),
            "created": str(attr.get("createdDate", ""))[:10],
            "released": str(attr.get("earliestReleaseDate") or "")[:10],
        })
    return out


def review_status(bundle_id: str, aid: Optional[str] = None) -> Dict[str, str]:
    """**いま審査に出ているもの／最後に配信されたもの**を1件ずつに畳んで返す。

    戻り値: {"bundle_id", "in_flight"(審査中・待ち・要対応。無ければ None),
             "live"(配信中。無ければ None), "latest"(いちばん新しいバージョン)}
    """
    IN_FLIGHT = ("WAITING_FOR_REVIEW", "IN_REVIEW", "PENDING_DEVELOPER_RELEASE",
                 "PENDING_APPLE_RELEASE", "PROCESSING_FOR_APP_STORE",
                 "REJECTED", "METADATA_REJECTED", "INVALID_BINARY")
    LIVE = ("READY_FOR_SALE", "READY_FOR_DISTRIBUTION")
    rows = versions(bundle_id, aid=aid)
    return {
        "bundle_id": bundle_id,
        "in_flight": next((r for r in rows if r["state"] in IN_FLIGHT), None),
        "live": next((r for r in rows if r["state"] in LIVE), None),
        "latest": rows[0] if rows else None,
    }


def max_build(bundle_id: str, aid: Optional[str] = None) -> int:
    """登録済みビルド番号の最大値。1件も無ければ 0。

    build番号が数字でないアプリ（"1.0.3" 形式）は無視する。
    """
    best = 0
    for b in builds(bundle_id, aid=aid):
        v = b["version"]
        if v.isdigit():
            best = max(best, int(v))
    return best


if __name__ == "__main__":
    import sys

    if not is_configured():
        print("未設定です。.env.appstore に ASC_KEY_ID / ASC_ISSUER_ID / ASC_PRIVATE_KEY_PATH を書いてください。")
        sys.exit(2)
    if len(sys.argv) > 1 and sys.argv[1] == "--review":
        # 全アプリの審査状況を一覧する（引数で bundle を絞ってもよい）
        targets = sys.argv[2:] or [a["bundleId"] for a in list_apps()]
        for bundle in targets:
            st = review_status(bundle)
            live = st["live"]
            flight = st["in_flight"]
            print("{:<40} 配信中 {:<8} 審査中のもの {}".format(
                bundle,
                (live or {}).get("version", "—"),
                "{} … {}".format(flight["version"], flight["state_ja"]) if flight else "なし"))
        sys.exit(0)
    if len(sys.argv) > 1 and sys.argv[1] != "--apps":
        bundle = sys.argv[1]
        print("{} の登録済み最大build番号: {}".format(bundle, max_build(bundle)))
        for b in builds(bundle)[:10]:
            print("   build {:<6} {}  {}".format(b["version"], b["uploadedDate"][:10], b["state"]))
    else:
        for a in list_apps():
            print("{:<12} {:<42} {}".format(a["id"], a["bundleId"], a["name"]))
