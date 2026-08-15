"""並列実行と「不要な工程を省く」仕組みの確認。

順番に流していた頃の作りに戻していないか（＝依存の無い部隊が同時に走るか）と、
成果物に要らない部隊を起動しないかを、実際にパイプラインを動かして確かめる。
"""
from __future__ import annotations

import threading
import time

from core.context import JobContext
from core.pipeline import PIPELINE_ORDER, Pipeline


def test_dependencies_form_a_valid_graph():
    """依存先が実在し、循環していないこと。"""
    from agents import build_default_agents

    agents = {a.key: a for a in build_default_agents()}
    for key, agent in agents.items():
        for dep in agent.depends_on:
            assert dep in agents, "%s の依存先 %s が存在しない" % (key, dep)

    resolved = set()
    for _ in range(len(agents) + 1):
        for key, agent in agents.items():
            if set(agent.depends_on) <= resolved:
                resolved.add(key)
    assert resolved == set(agents), "依存が循環している: %s" % (set(agents) - resolved)


def test_independent_agents_run_at_the_same_time():
    """レビューと法務のように依存の無い部隊が、同時刻に走っていること。"""
    events = []
    lock = threading.Lock()

    def record(event):
        if event.get("type") in ("agent_start", "agent_end"):
            with lock:
                events.append((time.time(), event["type"], event["agent"]))

    ctx = JobContext(brief="並列確認", options={"slide_count": 3}, on_event=record)
    Pipeline().run(ctx, only=["orchestrator", "planner", "reviewer", "legal"])

    spans = {}
    for ts, kind, key in events:
        spans.setdefault(key, {})[kind] = ts
    reviewer, legal = spans.get("reviewer"), spans.get("legal")
    assert reviewer and legal, "レビューと法務が実行されていない"
    overlap = (reviewer["agent_start"] < legal["agent_end"]
               and legal["agent_start"] < reviewer["agent_end"])
    assert overlap, "レビューと法務が同時に走っていない（直列に戻っている）"


def test_unneeded_agents_are_not_started():
    """チラシ1枚のように動画が不要な依頼で、動画・音声部隊を起動しないこと。"""
    started = []
    ctx = JobContext(
        brief="チラシを1枚作りたい",
        options={"slide_count": 3, "targets": ["pptx"]},
        on_event=lambda e: started.append(e["agent"]) if e.get("type") == "agent_start" else None,
    )
    Pipeline().run(ctx)

    assert "ppt" in started
    assert "voice" not in started, "不要な音声部隊が動いている"
    assert "video" not in started, "不要な動画部隊が動いている"
    assert "publisher" not in started, "不要なSNS部隊が動いている"
    assert "orchestrator" in started and "acceptance" in started, "常時実行の部隊が落ちている"


def test_display_order_covers_every_agent():
    from agents import build_default_agents

    keys = {a.key for a in build_default_agents()}
    assert set(PIPELINE_ORDER) == keys, "表示順と登録部隊がずれている"
