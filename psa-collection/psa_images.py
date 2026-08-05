"""PSAカード画像の取得とローカルキャッシュ。

画像の入手経路は2つ。どちらも `data/images/<証明書番号>[_back].jpg` に貯め、
一度取れた画像は再取得しない。

1. PSA公開API（https://api.psacard.com/publicapi/）… 無料トークンで1日100件まで
2. 手動（アップロード / ファイル名が証明書番号の画像をフォルダごと取込）

PSAの証明書ページ自体はCloudflareで保護されておりスクレイピング不可のため、
自動取得はAPI経由のみ。
"""

import json
import re
from datetime import date
from pathlib import Path

import requests

API_BASE = "https://api.psacard.com/publicapi"
DAILY_LIMIT = 100  # 無料枠。超えると429が返る
TIMEOUT = 20


class ImageStore:
    """証明書番号をキーに表・裏の画像ファイルを管理する。"""

    def __init__(self, data_dir: Path):
        self.dir = data_dir / "images"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.state_path = data_dir / "image_state.json"
        self.urls_path = data_dir / "image_urls.json"

    # ------------------------------------------------------------ ファイル

    def path(self, cert: str, back: bool = False) -> Path:
        return self.dir / f"{cert}{'_back' if back else ''}.jpg"

    def has(self, cert: str) -> bool:
        return self.path(cert).exists()

    def get(self, cert: str, back: bool = False):
        p = self.path(cert, back)
        return p if p.exists() else None

    def save_bytes(self, cert: str, data: bytes, back: bool = False) -> Path:
        p = self.path(cert, back)
        p.write_bytes(data)
        return p

    def cached_certs(self) -> set:
        """ローカルに画像があるか、少なくとも画像URLが分かっている証明書番号。"""
        local = {p.stem for p in self.dir.glob("*.jpg") if not p.stem.endswith("_back")}
        return local | set(self._urls())

    # ------------------------------------------------------------ 画像URL
    # 画像ファイルのダウンロードに失敗しても、URLが分かっていればブラウザ側で
    # 直接表示できるため、APIから得たURLは必ず控えておく。

    def _urls(self) -> dict:
        if self.urls_path.exists():
            return json.loads(self.urls_path.read_text(encoding="utf-8"))
        return {}

    def set_urls(self, cert: str, front: str = "", back: str = "") -> None:
        urls = self._urls()
        entry = urls.get(cert, {})
        if front:
            entry["front"] = front
        if back:
            entry["back"] = back
        urls[cert] = entry
        self.urls_path.write_text(
            json.dumps(urls, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def url(self, cert: str, back: bool = False):
        return self._urls().get(cert, {}).get("back" if back else "front")

    def source(self, cert: str, back: bool = False):
        """表示に使えるもの（ローカルパス優先、無ければURL）を返す。"""
        p = self.path(cert, back)
        if p.exists():
            return str(p)
        return self.url(cert, back)

    # ------------------------------------------------------------ 取得状態

    def _state(self) -> dict:
        if self.state_path.exists():
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        return {"date": "", "count": 0, "failed": {}}

    def _write_state(self, state: dict) -> None:
        self.state_path.write_text(
            json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def used_today(self) -> int:
        """今日すでにAPIを何回呼んだか（日付が変われば0に戻る）。"""
        state = self._state()
        return state["count"] if state.get("date") == date.today().isoformat() else 0

    def remaining_today(self) -> int:
        return max(0, DAILY_LIMIT - self.used_today())

    def _count_call(self, n: int = 1) -> None:
        state = self._state()
        today = date.today().isoformat()
        if state.get("date") != today:
            state["date"], state["count"] = today, 0
        state["count"] += n
        self._write_state(state)

    def failed_certs(self) -> dict:
        """画像が存在しなかった等で取得できなかった証明書番号 → 理由。"""
        return self._state().get("failed", {})

    def _mark_failed(self, cert: str, reason: str) -> None:
        state = self._state()
        state.setdefault("failed", {})[cert] = reason
        self._write_state(state)

    def clear_failed(self) -> None:
        state = self._state()
        state["failed"] = {}
        self._write_state(state)


# ---------------------------------------------------------------- API取得

def _extract_images(payload) -> list:
    """APIレスポンスから (画像URL, 裏面か) を拾う。

    PSA側のフィールド名の揺れ（ImageURL / imageUrl、IsFrontImage / isFrontImage）に
    耐えるよう、辞書を再帰的に走査して画像URLらしきものを集める。
    """
    found = []

    def walk(node):
        if isinstance(node, dict):
            url = next(
                (
                    v for k, v in node.items()
                    if isinstance(v, str)
                    and "image" in k.lower() and re.match(r"https?://", v)
                ),
                None,
            )
            if url:
                is_front = next(
                    (bool(v) for k, v in node.items() if "front" in k.lower()), True
                )
                found.append((url, not is_front))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(payload)
    # 同一URLの重複を除く（順序は保つ）
    seen, out = set(), []
    for url, back in found:
        if url not in seen:
            seen.add(url)
            out.append((url, back))
    return out


def fetch_one(cert: str, token: str, store: ImageStore) -> tuple[bool, str]:
    """1件分の画像をAPIから取得して保存。(成功したか, メッセージ) を返す。"""
    headers = {"Authorization": f"bearer {token}"}
    try:
        r = requests.get(
            f"{API_BASE}/cert/GetImagesByCertNumber/{cert}",
            headers=headers, timeout=TIMEOUT,
        )
    except requests.RequestException as e:
        return False, f"通信エラー: {e}"

    store._count_call()

    if r.status_code == 429:
        return False, "QUOTA"  # 呼び出し側で打ち切る合図
    if r.status_code in (401, 403):
        return False, "AUTH"
    if r.status_code != 200:
        store._mark_failed(cert, f"HTTP {r.status_code}")
        return False, f"HTTP {r.status_code}"

    try:
        images = _extract_images(r.json())
    except ValueError:
        store._mark_failed(cert, "JSONではない応答")
        return False, "JSONではない応答"

    if not images:
        store._mark_failed(cert, "画像なし")
        return False, "画像なし"

    saved = 0
    for url, is_back in images[:2]:  # 表・裏の2枚まで
        # URLは先に控える。ダウンロードに失敗してもブラウザ側で直接表示できる
        store.set_urls(cert, back=url) if is_back else store.set_urls(cert, front=url)
        try:
            img = requests.get(url, timeout=TIMEOUT)
            if img.status_code == 200 and img.content:
                store.save_bytes(cert, img.content, back=is_back)
                saved += 1
        except requests.RequestException:
            continue

    if saved == 0:
        return True, "URLのみ取得（画像はPSAから直接表示）"
    return True, f"{saved}枚"


def fetch_many(certs, token: str, store: ImageStore, progress=None) -> dict:
    """未取得の証明書番号をまとめて取得。日次上限に達したら止める。"""
    result = {"ok": 0, "ng": 0, "messages": [], "stopped": None}
    todo = [c for c in certs if not store.has(c)]

    for i, cert in enumerate(todo):
        if store.remaining_today() <= 0:
            result["stopped"] = "日次上限(100件)に達しました。明日また実行してください。"
            break
        ok, msg = fetch_one(cert, token, store)
        if ok:
            result["ok"] += 1
        else:
            if msg == "QUOTA":
                result["stopped"] = "PSA側の日次上限に達しました。明日また実行してください。"
                break
            if msg == "AUTH":
                result["stopped"] = "トークンが無効です。PSAの開発者ページで再発行してください。"
                break
            result["ng"] += 1
            result["messages"].append(f"{cert}: {msg}")
        if progress:
            progress(i + 1, len(todo), cert)

    return result
