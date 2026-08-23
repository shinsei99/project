"""アイテム: PDFを向きを直して読む（既存の共有モジュール pdf_orient.py を利用）

不動産の資料は横向き・上下逆のスキャンが普通に混ざる。そのまま渡すとAIが誤読するため、
先に向きを直す。実装は既に3アプリで動いているものをそのまま使う（作り直さない）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import List, Optional, Tuple

NAME = "pdf_read"
LABEL = "PDFの向き補正・画像化"
DESCRIPTION = "スキャンPDFの向き（横倒し・逆さ）を直してから読む。謄本・重説・マイソク向け"

HOME = Path(__file__).resolve().parent.parent.parent
# 2026-08-23: 実体は**リポジトリ直下の pdf_orient.py** に集約した。
# 各アプリ配下のものは委譲だけになったので、直下を最優先で見る（残りは古い環境向けの保険）。
CANDIDATES = [HOME / "pdf_orient.py",
              HOME / "restoration-calculator" / "pdf_orient.py",
              HOME / "maisoku-converter" / "pdf_orient.py",
              HOME / "building-manager" / "pdf_orient.py"]


def _module_path() -> Optional[Path]:
    for path in CANDIDATES:
        if path.exists():
            return path
    return None


def available() -> Tuple[bool, str]:
    path = _module_path()
    if not path:
        return False, "pdf_orient.py が見つかりません"
    try:
        _load(path)
    except Exception as exc:
        return False, "読み込み失敗: %s" % str(exc)[:60]
    return True, "既存の共有モジュールを使います（%s）" % path.parent.name


def _load(path: Path):
    spec = importlib.util.spec_from_file_location("pdf_orient_shared", str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def upright_images(pdf_path, out_dir) -> List[str]:
    """PDFを向きを直したページ画像にして、そのパス一覧を返す。"""
    path = _module_path()
    if not path:
        raise RuntimeError("pdf_orient.py が見つかりません")
    module = _load(path)
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    data = Path(pdf_path).read_bytes()
    return module.upright_page_images(data, str(out_dir))
