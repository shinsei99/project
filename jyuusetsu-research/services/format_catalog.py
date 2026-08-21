"""書式カタログ — レジストリを読み、画面へ「カテゴリ→書式」を提供し、出力する。

Excel と Word で流し込みの仕組みが違う（片方は色と数式、片方は表のセル）ので、
呼び分けはここに閉じ込め、画面側は `generate()` を呼ぶだけにする。

レジストリは `scan_formats.py` が作る `data/format_registry.json`。
**無ければ画面は「書類雛形フォルダが見つからない」と出して止まる**（黙って
古い同梱テンプレートに落ちない）。以前アプリに同梱していたテンプレートは
他社の実案件が記入済みで、前の案件の情報が混ざった書類が出る状態だったため。
"""

from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

from services import docx_format_service as dfs
from services import official_format_service as ofs

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(BASE_DIR, "data", "format_registry.json")

# 画面に出す順。実務で使う頻度が高いものを上に。
CATEGORY_ORDER = [
    "excel版自動入力書式（売買契約書・重要事項説明書）",
    "重要事項説明書",
    "売買契約書",
    "賃貸借契約書",
    "媒介契約書",
    "付帯設備表及び物件状況確認書（告知書）",
    "管理委託・サブリース書式",
    "書面の電磁的方法による提供及びIT重説関係書式等",
    "取引台帳・従業者証明書・宅地建物取引業者票等",
    "犯罪収益移転防止法 関連様式",
    "インボイス制度関連書式等",
    "その他の書式",
]

_cache: Optional[dict] = None


def load(force: bool = False) -> dict:
    global _cache
    if _cache is not None and not force:
        return _cache
    if not os.path.exists(REGISTRY_PATH):
        _cache = {"root": "", "formats": []}
        return _cache
    with open(REGISTRY_PATH, encoding="utf-8") as fh:
        _cache = json.load(fh)
    return _cache


def available() -> bool:
    reg = load()
    return bool(reg["formats"]) and os.path.isdir(reg.get("root", ""))


def status_message() -> str:
    reg = load()
    if not reg["formats"]:
        return (
            "書式レジストリがありません。`.venv/bin/python scan_formats.py` を実行して "
            "`data/format_registry.json` を作ってください。"
        )
    if not os.path.isdir(reg.get("root", "")):
        return "書類雛形フォルダが見つかりません: {}".format(reg.get("root"))
    return ""


def categories() -> List[str]:
    present = {f["category"] for f in load()["formats"]}
    ordered = [c for c in CATEGORY_ORDER if c in present]
    return ordered + sorted(present - set(ordered))


def formats_in(category: str) -> List[dict]:
    """カテゴリ内の書式。対応項目が多いものを上に出す（使いやすい順）。"""
    items = [f for f in load()["formats"] if f["category"] == category]

    def score(f):
        return len(f.get("mapping") or f.get("fields") or [])

    return sorted(items, key=lambda f: (-score(f), f["name"]))


# 同梱シートのうち「書類」ではないもの（参照表・入力手引き）。件数に数えない。
NON_DOCUMENT = re.compile(r"^入力|^リスト$|保証協会一覧表|地方本部一覧")


def document_sheets(entry: dict):
    return [s for s in entry.get("sheets", []) if not NON_DOCUMENT.search(s)]


def label(entry: dict) -> str:
    n = len(entry.get("mapping") or entry.get("fields") or [])
    kind = "Excel" if entry.get("kind") == "xlsx" else "Word"
    extra = ""
    if entry.get("fanout_count"):
        # 1ファイルで複数の書類が同時に仕上がる（重説→契約書へ数式で波及する）
        docs = document_sheets(entry)
        if len(docs) > 1:
            extra = "・{}書類同梱".format(len(docs))
    return "{}（{}／自動入力 {}項目{}）".format(entry["name"], kind, n, extra)


def source_path(entry: dict) -> str:
    return os.path.join(load()["root"], entry["path"])


def generate(entry: dict, data: Dict[str, str], out_dir: str) -> str:
    """PropertyData を書式へ流し込み、出力パスを返す。"""
    src = source_path(entry)
    if not os.path.exists(src):
        raise FileNotFoundError("書式が見つかりません: {}".format(src))
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, "作成_" + entry["name"])

    if entry.get("kind") == "docx":
        return dfs.fill(src, dst, data, targets=entry.get("targets"))

    cells = {cell: data.get(field, "") for field, cell in (entry.get("mapping") or {}).items()}
    return ofs.fill(src, dst, entry["driver"], cells)


def filled_fields(entry: dict, data: Dict[str, str]) -> List[str]:
    """実際に値が入る項目（空の項目は書式の既定を残すので数えない）。"""
    keys = list((entry.get("mapping") or {}).keys()) or list(entry.get("fields") or [])
    return [k for k in keys if str(data.get(k, "") or "").strip()]
