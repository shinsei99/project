# -*- coding: utf-8 -*-
"""会社の壁（2026-08-30 オーナー指示）。

**大京商事株式会社と新誠プロパティマネジメント株式会社の情報を、絶対に混ぜない。**

入口（ルーム／チャネル）ごとにどちらの会社の場かが決まっていて、
その場からは**自社のものと共通のものしか見えない**。双方向。

    全体チャットワーク(349546270) … 大京商事株式会社
    鷲見さん個人チャット(444751421) … 新誠プロパティマネジメント株式会社
    LINE                          … 大京商事株式会社

設定は `room_company_map`（管理画面から変更可）。

★守り方は「プロンプトでお願いする」ではなく **SQL・条件分岐で見えなくする**。
  見えないものは漏らせない。プロンプトは取り違え防止の補助に留める。

★道具は別プロセス（agent_tool.py）で動くので、qa.py が env_extra で
  `CWAI_COMPANY` / `CWAI_ROOM_ID` を渡している。
  分からないときは**既定の会社に倒す**＝もう一方の会社の情報は出さない側で止まる。

共通で使ってよいもの（会社で分けない）:
  法令・判例・書籍（knowledge_documents.company = '共通'）、
  e-Gov・e-Stat・不動産情報ライブラリ・GIS・郵便番号などの外部API。
"""
from __future__ import annotations

import json
import os

SHARED = "共通"


def _map() -> dict:
    from services.settings import get_setting
    try:
        return json.loads(get_setting("room_company_map", "") or "{}")
    except Exception:
        return {}


def default_company() -> str:
    return _map().get("default") or ""


def here() -> str:
    """いまどの会社の場から呼ばれているか。分からなければ既定の会社。"""
    c = (os.environ.get("CWAI_COMPANY") or "").strip()
    if c:
        return c
    rid = (os.environ.get("CWAI_ROOM_ID") or "").strip()
    m = _map()
    return (m.get("rooms", {}) or {}).get(rid) or m.get("default") or ""


def company_of_room(room_id) -> str:
    m = _map()
    return (m.get("rooms", {}) or {}).get(str(room_id)) or m.get("default") or ""


def own_rooms() -> set:
    """いまの会社の入口になっているルーム。"""
    me = here()
    m = _map()
    return {int(k) for k, v in (m.get("rooms", {}) or {}).items()
            if v == me and str(k).isdigit()}


def other_rooms() -> set:
    """いまの会社**以外**のルーム。見せない・書かない。"""
    me = here()
    if not me:
        return set()
    m = _map()
    return {int(k) for k, v in (m.get("rooms", {}) or {}).items()
            if v != me and str(k).isdigit()}


def blocks_room(room_id) -> bool:
    """このルームは、いまの場から触ってはいけないか。"""
    try:
        return int(room_id or 0) in other_rooms()
    except (TypeError, ValueError):
        return False


def deny(room_id=None, what="この情報") -> dict:
    """道具が返す拒否の形（理由を必ず書く。黙って空を返さない）。"""
    msg = f"別の会社のものなので、ここからは扱えません（いまの会社={here() or '不明'}"
    if room_id is not None:
        msg += f"／対象ルーム={room_id}"
    return {"ok": False, "error": msg + f"）。{what}は、その会社の入口で扱ってください。"}


def is_default_company() -> bool:
    """いまの場が既定の会社（＝共有フォルダ・案件などの持ち主）か。"""
    d = default_company()
    return (not d) or here() == d
