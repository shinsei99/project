"""商圏データ（e-Stat）— **実体は直下の共有モジュール `area_stats.py`**。

2026-08-23: 事業計画案ジェネレーター（8533）でも同じ数字を使うことにしたため、
計算とまとめ方を直下へ移した。ここは import 経路を変えないための薄い橋渡し。
**ここに計算を書き足さないこと**（2箇所に分かれると、同じ物件で違う空き家率が出る）。
"""

import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from area_stats import fetch, is_configured  # noqa: F401
