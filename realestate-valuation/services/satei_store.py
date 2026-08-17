# -*- coding: utf-8 -*-
"""作成中の査定内容を「任意の名前」で保存・呼び出しする簡易ストア。

入力一式（物件情報・取引事例・売出・加減点・流通性比率・説明書・顧客/日付/種別）を
1件のスナップショット(dict)として JSON に保存する。顧客名・住所を含むため
`saved_satei.json` は .gitignore 対象（公開リポジトリに出さない・各PCローカル保持）。
"""

from __future__ import annotations

import json
from pathlib import Path

_PATH = Path(__file__).resolve().parent.parent / "saved_satei.json"


def _load_all() -> dict:
    try:
        if _PATH.exists():
            data = json.loads(_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def _save_all(data: dict) -> None:
    _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_saved() -> list[str]:
    """保存名の一覧（五十音/文字コード順）。"""
    return sorted(_load_all().keys())


def save_satei(name: str, snapshot: dict) -> None:
    """name をキーにスナップショットを保存（既存は上書き）。"""
    name = (name or "").strip()
    if not name:
        return
    data = _load_all()
    data[name] = snapshot
    _save_all(data)


def load_satei(name: str) -> dict | None:
    """保存済みスナップショットを返す（無ければ None）。"""
    return _load_all().get(name)


def delete_satei(name: str) -> None:
    data = _load_all()
    if name in data:
        del data[name]
        _save_all(data)
