# -*- coding: utf-8 -*-
"""謄本パーサ — 実体はリポジトリ直下の共有モジュール `registry_parser.py`。

2026-08-21 に実体を直下へ移した。理由は、**同じ謄本パーサを重説アプリでも使うため**。
コピーを2本持つと、謄本の様式対応を片方だけ直したときにもう片方が古いままになる。

このファイルは後方互換のための薄い入口。`from services import registry_parser` の
呼び出し側は今までどおり動く。**ロジックはここに書かないこと。**

移設時に1つ直した: `CLAUDE_BIN` が `/opt/homebrew/bin/claude` 固定だったため、
Intel Mac や `~/.local/bin` にCLIを入れているPCでは見つからず、
**AI解析が黙って無効になり正規表現フォールバックだけで動いていた**（エラーも出ない）。
共有モジュール側で実体を探すようにした。
"""

import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from registry_parser import *  # noqa: F401,F403,E402
from registry_parser import (  # noqa: F401,E402  明示再輸出（* は _ 始まりを運ばない）
    CLAUDE_BIN,
    EMPTY,
    extract_text,
    parse_registry,
)
