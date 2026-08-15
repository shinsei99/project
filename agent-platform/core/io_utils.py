"""ファイル入出力まわりの小道具。"""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional


def ensure_dir(path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def write_text(path, text: str) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(text, encoding="utf-8")
    return p


def write_json(path, data: Any) -> Path:
    p = Path(path)
    ensure_dir(p.parent)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


def read_json(path, default: Optional[Any] = None) -> Any:
    p = Path(path)
    if not p.exists():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return default


def slugify(text: str, max_len: int = 40) -> str:
    """日本語混じりの文字列からファイル名向けの短い識別子を作る。

    日本語は情報が落ちるので、ASCII化できない文字は削り、
    結果が空になったら呼び出し側で連番などを足す前提。
    """
    normalized = unicodedata.normalize("NFKD", text)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^A-Za-z0-9]+", "-", ascii_only).strip("-").lower()
    return slug[:max_len]


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return "%.1f%s" % (size, unit)
        size /= 1024
    return "%.1fGB" % size
