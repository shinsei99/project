"""このアプリで作った紙面を「型」として登録する

なぜ要るか:
  型はこちらが先回りして用意したものだけでは足りない。実務で「今回のこの並びが良かった」
  は必ず出る。それを毎回1から作り直すのは無駄だし、良かった理由も残らない。

  **出来上がりを見て良かったものを、その場で型にする。** これができると、
  型は使うほど増える。増えた型は次の依頼のヒアリング候補に自動で並ぶ。

どう保存するか（重要）:
  紙面をそのまま画像で保存しても再利用できない。保存するのは**並びと寸法だけ**で、
  文字と写真は「役割の目印」に置き換える。
    例) {"block":"full_photo","photo":2}  →  {"block":"full_photo","photo":"@hero"}
        {"block":"note","text":"丸太を…"} →  {"block":"note","text":"@lead"}
  こうしておくと、別の物件の文言と写真を流し込んでも同じ並びで組める。

  目印に置き換えられない値（写真の高さ、列の比率など）は**そのまま残す**。
  そこがまさに「この型の良かったところ」だから。

保存先は knowledge/user_templates.json（gitignore。物件名などが混ざるため）。
"""
from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from .config import ROOT

STORE = ROOT / "knowledge" / "user_templates.json"

# 文言の目印。content のキーと、部品側のどの引数に入るか
TEXT_SLOTS = {
    "kicker": ("kicker",),
    "catch": ("catch", "text"),
    "title": ("title", "name"),
    "sub": ("sub", "access"),
    "price": ("price", "rent", "main"),
    "unit": ("unit",),
    "lead": ("text", "lead"),
}
LIST_SLOTS = {"badges": ("items",), "appeals": ("items",)}


def _load_raw() -> Dict[str, Any]:
    if not STORE.exists():
        return {}
    try:
        data = json.loads(STORE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (ValueError, OSError):
        return {}


def all_saved(orientation: str = "", genre: str = "") -> List[Dict[str, Any]]:
    items = [v for v in _load_raw().values() if isinstance(v, dict)]
    if orientation:
        items = [x for x in items if x.get("orientation", "portrait") == orientation]
    if genre:
        items = [x for x in items if genre in (x.get("genres") or ["promo"])]
    return items


def get(template_id: str) -> Optional[Dict[str, Any]]:
    item = _load_raw().get(str(template_id))
    return item if isinstance(item, dict) else None


def _slug(name: str) -> str:
    text = re.sub(r"[^0-9A-Za-z一-龠ぁ-んァ-ヶー]+", "_", str(name)).strip("_")
    return "saved_" + (text[:24] or "template")


def save(name: str, layout: List[Dict[str, Any]], content: Dict[str, Any],
         orientation: str = "portrait", genre: str = "promo",
         summary: str = "", best_for: str = "") -> Dict[str, Any]:
    """今の紙面を型として保存する。

    同じ名前で保存し直すと**上書き**する（試行錯誤して育てられるように）。
    """
    spec = {
        "id": _slug(name), "name": str(name).strip() or "名前のない型",
        "summary": summary.strip() or "このアプリで作った紙面から登録した型",
        "best_for": best_for.strip() or "登録時と似た内容のとき",
        "orientation": orientation, "genres": [genre], "source": "user",
        "photos_min": _count_photos(layout),
        "layout": _to_spec(layout, content),
    }
    data = _load_raw()
    data[spec["id"]] = spec
    STORE.parent.mkdir(parents=True, exist_ok=True)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return spec


def delete(template_id: str) -> bool:
    data = _load_raw()
    if template_id not in data:
        return False
    data.pop(template_id)
    STORE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return True


def _count_photos(layout) -> int:
    total = 0
    for item in _walk(layout):
        if "photo" in item:
            total += 1
        total += len(item.get("photos") or [])
    return max(total, 1)


def _walk(layout):
    for item in layout or []:
        if not isinstance(item, dict):
            continue
        yield item
        for side in ("left", "right"):
            for child in (item.get(side) or []):
                if isinstance(child, dict):
                    yield child


def _photo_roles(content) -> Dict[int, str]:
    """写真番号 → 役割。保存時に番号を役割へ置き換えるために使う。"""
    photos = (content or {}).get("photos") or {}
    roles = {}
    for key in ("hero", "floorplan"):
        try:
            roles[int(photos.get(key))] = "@" + key
        except (TypeError, ValueError):
            pass
    for index, number in enumerate((photos.get("rooms") or [])):
        try:
            roles.setdefault(int(number), "@room%d" % index)
        except (TypeError, ValueError):
            pass
    return roles


def _to_spec(layout, content) -> List[Dict[str, Any]]:
    """紙面 → 型。文言と写真を目印に置き換える。寸法や比率はそのまま残す。"""
    roles = _photo_roles(content)
    text_of = {}
    for key, _slots in TEXT_SLOTS.items():
        value = str((content or {}).get(key, "")).strip()
        if value:
            text_of[value] = "@" + key

    def convert(item):
        out = {}
        for key, value in item.items():
            if key in ("left", "right") and isinstance(value, list):
                out[key] = [convert(x) for x in value if isinstance(x, dict)]
            elif key == "photo":
                out[key] = roles.get(_int(value), value)
            elif key == "photos" and isinstance(value, list):
                out[key] = [roles.get(_int(x), x) for x in value]
            elif key == "rows":
                out[key] = "@spec_rows"
            elif key == "items" and item.get("block") == "badge_row":
                out[key] = "@badges"
            elif key == "items" and item.get("block") == "point_row":
                out[key] = "@appeals"
            elif isinstance(value, str) and value.strip() in text_of:
                out[key] = text_of[value.strip()]
            else:
                out[key] = value
        return out

    return [convert(x) for x in (layout or []) if isinstance(x, dict)]


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def build(template_id: str, content: Dict[str, Any]) -> List[Dict[str, Any]]:
    """保存した型に、別の内容を流し込んで紙面を組む。"""
    spec = get(template_id)
    if not spec:
        return []
    photos = (content or {}).get("photos") or {}
    rooms = [x for x in (photos.get("rooms") or [])]

    def photo_for(mark):
        if not isinstance(mark, str) or not mark.startswith("@"):
            return mark
        key = mark[1:]
        if key.startswith("room"):
            try:
                return rooms[int(key[4:])]
            except (ValueError, IndexError):
                return None
        return photos.get(key)

    def fill(item):
        out = {}
        for key, value in item.items():
            if key in ("left", "right") and isinstance(value, list):
                out[key] = [x for x in (fill(y) for y in value) if x]
            elif key == "photo":
                out[key] = photo_for(value)
            elif key == "photos" and isinstance(value, list):
                out[key] = [x for x in (photo_for(v) for v in value) if x]
            elif value == "@spec_rows":
                out[key] = content.get("spec_rows") or []
            elif value == "@badges":
                out[key] = content.get("badges") or []
            elif value == "@appeals":
                out[key] = content.get("appeals") or []
            elif isinstance(value, str) and value.startswith("@"):
                out[key] = content.get(value[1:], "")
            else:
                out[key] = value
        # 中身が空になった部品は落とす（空の帯や空の表が紙面に残らないように）
        if out.get("block") in ("photo_hero", "full_photo") and not out.get("photo"):
            return {}
        if out.get("block") in ("photo_row", "photo_grid") and not out.get("photos"):
            return {}
        return out

    built = [fill(x) for x in (spec.get("layout") or [])]
    # contact は登録時の会社の連絡先が入っているので、いまの発行者情報で上書きする
    for item in built:
        if item.get("block") == "contact_bar":
            item.update({k: v for k, v in (content.get("contact") or {}).items() if v})
    return [x for x in built if x]
