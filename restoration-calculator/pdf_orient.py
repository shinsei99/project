# -*- coding: utf-8 -*-
"""PDFの向き補正 — **実体はリポジトリ直下の `pdf_orient.py`**（2026-08-23 に集約）。

このファイルは import 経路を変えないための橋渡し。**ここに実装を書き足さないこと。**
2026-08-23 まで8つのアプリに同じ中身のコピーがあり、直すたびに8箇所を触る形だった
（1箇所忘れると「あのアプリだけ向きが直らない」になる）。

同じ名前のファイルなので `import pdf_orient` では自分自身を読んでしまう。
直下のファイルを**パス指定で**読み込んでいる（agent-platform/tools/pdf_read.py と同じ手）。
"""

import importlib.util as _ilu
import pathlib as _pathlib

_SHARED = _pathlib.Path(__file__).resolve().parents[1] / "pdf_orient.py"
if not _SHARED.exists():
    raise ImportError(
        "共有モジュールが見つかりません: {}（リポジトリ直下の pdf_orient.py が必要です）".format(_SHARED))

_spec = _ilu.spec_from_file_location("pdf_orient_shared", str(_SHARED))
_mod = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

ensure_upright_pdf = _mod.ensure_upright_pdf
ensure_upright_image = _mod.ensure_upright_image
ensure_upright_bytes = _mod.ensure_upright_bytes
upright_page_images = _mod.upright_page_images

ORIENT_MODEL = _mod.ORIENT_MODEL
RENDER_DPI = _mod.RENDER_DPI
THUMB_MAX = _mod.THUMB_MAX
MAX_PAGES = _mod.MAX_PAGES
ORIENT_TIMEOUT = _mod.ORIENT_TIMEOUT
TEXT_MIN_CHARS = _mod.TEXT_MIN_CHARS
