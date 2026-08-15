"""部隊の登録。

画像は `visuals`（実写真＋HTML作図・無料）を使う。
`image_generator`（DALL-E / Gemini画像 / Stability）は**有料のため既定では登録しない**。
`qa`（テスト・QA部隊）は廃止。ファイルの有無しか見ておらず、
中身が依頼どおりかは `acceptance`（司令塔の最終確認）が見る。
使う場合はここに import を足し、`.env` で AP_ALLOW_PAID=1 にすること。

各モジュールを import すると `@register` でレジストリに載る。
実行順は core/pipeline.py の PIPELINE_ORDER が決める。
"""
from __future__ import annotations

from typing import List

from core.base_agent import AGENT_REGISTRY

from . import (  # noqa: F401  (import した時点で登録される)
    acceptance,
    flyer_builder,
    visuals,
    legal,
    orchestrator,
    planner,
    poster,
    ppt_builder,
    publisher,
    researcher,
    reviewer,
    supervisor,
    video_editor,
    voice,
)


def build_default_agents() -> List:
    """登録済みの全エージェントを1つずつ生成して返す。"""
    return [cls() for cls in AGENT_REGISTRY]


def agent_catalog() -> List[dict]:
    """画面表示用の部隊一覧（UIのステータスボードが使う）。"""
    from core.pipeline import PIPELINE_ORDER

    by_key = {cls.key: cls for cls in AGENT_REGISTRY}
    ordered = [by_key[k] for k in PIPELINE_ORDER if k in by_key]
    return [{"key": c.key, "name_ja": c.name_ja, "role_ja": c.role_ja,
             "icon": c.icon, "uses": c.uses} for c in ordered]
