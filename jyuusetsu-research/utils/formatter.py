"""表示・出力用のフォーマット補助。"""

from typing import Dict


def safe(value: str, placeholder: str = "（取得できませんでした）") -> str:
    """空文字を分かりやすいプレースホルダに置き換える（表示用）。"""
    value = (value or "").strip()
    return value if value else placeholder


def section_basic(data: Dict[str, str]) -> Dict[str, str]:
    return {
        "所在地": data.get("所在地", ""),
        "地番": data.get("地番", ""),
        "家屋番号": data.get("家屋番号", ""),
        "地目": data.get("地目", ""),
        "地積": data.get("地積", ""),
        "種類": data.get("種類", ""),
        "構造": data.get("構造", ""),
        "床面積": data.get("床面積", ""),
    }


def section_city_planning(data: Dict[str, str]) -> Dict[str, str]:
    return {
        "用途地域": data.get("用途地域", ""),
        "建ぺい率": data.get("建ぺい率", ""),
        "容積率": data.get("容積率", ""),
        "防火地域": data.get("防火地域", ""),
        "高度地区": data.get("高度地区", ""),
    }


def section_areas(data: Dict[str, str]) -> Dict[str, str]:
    """区域指定（2026-08-23 追加）。重説の法令制限欄の下調べに使う。"""
    return {
        "地区計画": data.get("地区計画", ""),
        "都市計画道路": data.get("都市計画道路", ""),
        "急傾斜地崩壊危険区域": data.get("急傾斜地崩壊危険区域", ""),
        "地すべり防止区域": data.get("地すべり防止区域", ""),
        "自然公園": data.get("自然公園", ""),
        "立地適正化計画区域": data.get("立地適正化計画区域", ""),
    }


def section_hazard(data: Dict[str, str]) -> Dict[str, str]:
    return {
        "洪水浸水想定": data.get("洪水浸水想定", ""),
        "土砂災害": data.get("土砂災害", ""),
        "津波": data.get("津波", ""),
        "高潮浸水想定": data.get("高潮浸水想定", ""),
    }


def section_environment(data: Dict[str, str]) -> Dict[str, str]:
    return {
        "最寄駅": data.get("最寄駅", ""),
        "駅距離": data.get("駅距離", ""),
        "人口": data.get("人口", ""),
        "世帯数": data.get("世帯数", ""),
        "路線価": data.get("路線価", ""),
        "公示地価": data.get("公示地価", ""),
    }


def section_registry(data: Dict[str, str]) -> Dict[str, str]:
    """登記の要点。抵当権は**土地と建物を分けて出す**（重説の欄が分かれているため）。

    どちらの不動産のものか分からないときだけ、旧来の `抵当権` を「（土地・建物の別が
    不明）」として出す。書式には入らないので、画面で人に気づかせる必要がある。
    """
    out = {
        "所有者": data.get("所有者", ""),
        "抵当権（土地）": data.get("土地抵当権", ""),
        "抵当権（建物）": data.get("建物抵当権", ""),
    }
    if data.get("抵当権") and not (data.get("土地抵当権") or data.get("建物抵当権")):
        out["抵当権（土地・建物の別が不明）"] = data.get("抵当権", "")
    return out
