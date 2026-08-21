# -*- coding: utf-8 -*-
"""特約条項カタログ — 実体はリポジトリ直下の共有モジュール `tokuyaku_clauses.py`。

2026-08-21 に実体を直下へ移した。**重説アプリ（jyuusetsu-research）でも同じ
カタログを使うため。** コピーを2本持つと、片方だけ直した特約が契約書に載る。

このファイルは後方互換のための薄い入口。`from clauses import CATEGORIES, find_item`
は今までどおり動く。**項目をここに書き足さないこと。**
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tokuyaku_clauses import CATEGORIES, all_items, find_item  # noqa: F401,E402
