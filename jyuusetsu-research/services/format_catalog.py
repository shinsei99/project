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


def categories(deal: Optional[str] = None) -> List[str]:
    """取引種別を渡すと、**その種別の書式が1本も無い分類は出さない**
    （賃貸なのに「売買契約書」が並ぶのを止めるため。2026-08-21 オーナー指示）。"""
    formats = [f for f in load()["formats"] if _match_deal(f, deal)]
    present = {f["category"] for f in formats}
    ordered = [c for c in CATEGORY_ORDER if c in present]
    return ordered + sorted(present - set(ordered))


# 実務でセットにする4点（2026-08-21 オーナー指示）。
#
#   重説 ／ 契約書 ／ 付帯設備表 ／ 物件状況確認書（告知書）
#
# 売買では **重説と契約書は1ファイルに同梱されている**（全宅連の excel版自動入力書式。
# 重説に入力すると契約書へ自動転記される作り）。付帯設備表と物件状況確認書は別ファイルで、
# **どちらも自動入力の対象欄が無い**（売主が現況を書く書類なので白紙で出すのが正しい）。
# したがって売買の4点は **3ファイル** になる。
#
# 賃貸には付帯設備表・物件状況確認書の全宅連書式が無い（売買用のみ）ので2点。
PRESETS = {
    ("売買", "土地・戸建て"): [
        "【ファイル14】土地建物公簿用",              # 重説＋契約書＋引渡書ほか5書類
        "付帯設備表（土地建物用）",
        "物件状況確認書（告知書／土地建物・土地用）",
    ],
    ("売買", "区分所有（マンション）"): [
        "【ファイル15】区分所有建物用（敷地権）",     # 重説＋契約書ほか8書類
        "付帯設備表（区分所有建物用）",
        "物件状況確認書（告知書／区分所有建物用）",
    ],
    ("賃貸", "土地・戸建て"): [
        "建物貸借用 （住宅用）",
        "住宅賃貸借契約書（A）",
    ],
    ("賃貸", "区分所有（マンション）"): [
        "建物貸借用 （住宅用）",
        "住宅賃貸借契約書（A）",
    ],
}

PROPERTY_KINDS = ["土地・戸建て", "区分所有（マンション）"]


def preset(deal: str, kind: str) -> List[dict]:
    """取引種別と物件種別から「セットで作る書式」を返す。

    名前の一部で引く（書式名には【更新】2026年4月 のような版が付くため）。
    **同名が複数あるときは最初の1本**。見つからないものは黙って飛ばさず、
    呼び出し側が件数の差で気づけるよう、単に含めない（画面で件数を出している）。
    """
    names = PRESETS.get((deal, kind), [])
    formats = load().get("formats", [])
    out, used = [], set()
    for needle in names:
        # **前方一致を先に見る。** 部分一致だけだと「住宅賃貸借契約書（A）」で
        # 「**サブリース**住宅賃貸借契約書（A）」を拾ってしまう（2026-08-21 実測）
        cand = ([f for f in formats if f["name"].startswith(needle)]
                or [f for f in formats if needle in f["name"]])
        for f in cand:
            if f["path"] not in used:
                out.append(f)
                used.add(f["path"])
                break
    return out


# 取引種別の絞り込み（2026-08-21 オーナー指示）。
# 賃貸を選んでいるのに売買の書類が並ぶのは事故のもと（間違った書式で作ってしまう）。
#
# 分類だけでは決まらないものがある。**重要事項説明書には売買用と貸借用が同居**し、
# 媒介契約書も売買用と賃貸用がある。そこで「分類で決まるもの」は分類で、
# 決まらないものは**書式名の語**で判定する。
#
# 「共通」は両方に出す（犯収法の様式・取引台帳など、取引種別に関係ない書類）。
_DEAL_BY_CATEGORY = {
    "excel版自動入力書式（売買契約書・重要事項説明書）": "売買",
    "売買契約書": "売買",
    "付帯設備表及び物件状況確認書（告知書）": "売買",
    "建築条件付土地売買契約における建物建築・引渡し等に関する業務委託契約書": "売買",
    "賃貸借契約書": "賃貸",
    "管理委託・サブリース書式": "賃貸",
}
# 分類で決まらないとき、名前に含まれる語で判定する
_RENT_WORDS = ("貸借", "賃貸", "借地", "サブリース", "定期建物")
_SALE_WORDS = ("売買", "交換", "売渡", "買付", "購入", "売却")


def deal_of(entry: dict) -> str:
    """その書式が「売買」「賃貸」「共通」のどれか。"""
    by_cat = _DEAL_BY_CATEGORY.get(entry.get("category", ""))
    if by_cat:
        return by_cat
    name = entry.get("name", "")
    rent = any(w in name for w in _RENT_WORDS)
    sale = any(w in name for w in _SALE_WORDS)
    if rent and not sale:
        return "賃貸"
    if sale and not rent:
        return "売買"
    return "共通"      # どちらとも取れる／取引種別に関係ない書類


def _match_deal(entry: dict, deal: Optional[str]) -> bool:
    if not deal:
        return True
    d = deal_of(entry)
    return d == deal or d == "共通"


def by_path() -> Dict[str, dict]:
    """path -> 書式。画面が「選んだ書式」を分類をまたいで持ち回るために使う
    （選択の実体を path で持てば、分類を切り替えても選択が消えない）。"""
    return {f["path"]: f for f in load().get("formats", [])}


def formats_in(category: str, deal: Optional[str] = None) -> List[dict]:
    """カテゴリ内の書式。対応項目が多いものを上に出す（使いやすい順）。"""
    items = [f for f in load()["formats"]
             if f["category"] == category and _match_deal(f, deal)]

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
