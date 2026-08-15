"""発行者情報（会社名・住所・電話など）

なぜ設定に持つか:
  チラシにも掲示物にも送付書にも、**毎回同じ発行者情報**が入る。
  依頼のたびに打ち込むのは無駄だし、打ち間違えると外に出る印刷物が間違う。
  一度登録すれば、以降すべての成果物に自動で入る。

  逆に「スライドの枚数」「音量」のような**成果物ごとに変わるもの**は設定に置かない。
  それは依頼文や司令塔の確認で決まるべきもの。

`config/company.json` に保存する。個人情報・連絡先を含むため gitignore。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from .config import ROOT

STORE = ROOT / "config" / "company.json"

# 画面に出す項目（キー, ラベル, 説明）
FIELDS = [
    ("name", "会社名", "例: 大京商事株式会社"),
    ("department", "部署・担当", "例: 賃貸管理部　山田"),
    ("zip", "郵便番号", "例: 000-0000"),
    ("address", "住所", "例: 大阪府大阪市…"),
    ("tel", "電話番号", "例: 06-0000-0000"),
    ("fax", "FAX", "任意"),
    ("email", "メール", "任意"),
    ("license", "免許番号", "例: 大阪府知事（1）第00000号　※不動産広告に必要"),
    ("hours", "営業時間・定休日", "例: 9:00〜18:00／水曜定休"),
    ("website", "サイト", "任意"),
]


def load() -> Dict[str, Any]:
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def save(data: Dict[str, Any]) -> Path:
    cleaned = {key: str(data.get(key, "")).strip() for key, _, _ in FIELDS}
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    return STORE


def is_set() -> bool:
    data = load()
    return bool(data.get("name") or data.get("tel"))


def contact_lines() -> list:
    """連絡先ブロックに入れる行。空の項目は出さない。"""
    data = load()
    lines = []
    if data.get("name"):
        lines.append(data["name"] + ("　" + data["department"] if data.get("department")
                                     else ""))
    if data.get("tel"):
        tel = "TEL %s" % data["tel"]
        if data.get("fax"):
            tel += "　FAX %s" % data["fax"]
        lines.append(tel)
    for key in ("hours", "address", "email", "website"):
        if data.get(key):
            lines.append(data[key])
    return lines


def describe_for_prompt() -> str:
    """制作部隊に渡す発行者情報。

    ここに無い連絡先を部隊が勝手に作らないよう、「登録が無ければ記入欄にする」と
    はっきり伝える（過去に架空の電話番号を書いた事故を防ぐ）。
    """
    data = load()
    if not is_set():
        return ("【発行者情報】未登録です。**会社名・電話番号・免許番号を勝手に作らないこと。**\n"
                "その3つだけ blanks（記入欄）にしてください。\n"
                "**物件の条件（賃料・間取り・面積・所在地など）は記入欄にしないこと。**"
                "調査で分かっているものは、そのまま数値を書いてください。")
    lines = ["【発行者情報（そのまま印刷してよい確定情報）】"]
    for key, label, _ in FIELDS:
        if data.get(key):
            lines.append("- %s: %s" % (label, data[key]))
    lines.append("連絡先を載せる紙面では、この情報を contact ブロックに入れてください。")
    if data.get("license"):
        lines.append("不動産の広告では免許番号の表示が要ります。必ず入れてください。")
    return "\n".join(lines)
