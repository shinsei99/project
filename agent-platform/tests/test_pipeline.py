"""パイプライン全体が、APIキー無しでも最後まで通ることを確認する。

外部APIを一切使えない状態（conftest で強制）でも、
雛形の成果物を作りながら11工程を完走できることが、この基盤の前提条件。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from core.pipeline import PIPELINE_ORDER, Pipeline


def test_registry_covers_pipeline_order():
    from agents import build_default_agents

    keys = {a.key for a in build_default_agents()}
    assert set(PIPELINE_ORDER) <= keys, "実行順に登録されていない部隊がある"
    assert len(keys) >= 11, "部隊が11未満: %s" % keys


def test_dry_run_lists_all_steps(ctx):
    results = Pipeline().run(ctx, dry_run=True)
    assert len(results) == len(PIPELINE_ORDER)
    assert all(r.ok for r in results)


def test_offline_pipeline_produces_core_artifacts(ctx):
    """キー無しでも、計画・原稿・画像・パワポまでは必ず出来ること。"""
    pytest.importorskip("pptx")
    pytest.importorskip("PIL")

    results = Pipeline().run(ctx, skip=["video", "acceptance"])
    assert all(r.ok for r in results), [r.error for r in results if not r.ok]

    assert ctx.state["plan"]["slide_count"] == 3
    assert len(ctx.state["deck"]["slides"]) == 3
    assert len(ctx.state["images"]) == 3

    pptx_path = Path(ctx.root) / ctx.state["pptx"]
    assert pptx_path.exists() and pptx_path.stat().st_size > 0

    report = Path(ctx.state["report_path"])
    assert report.exists()
    assert "実行レポート" in report.read_text(encoding="utf-8")


def test_events_are_japanese_and_ordered():
    """画面に出る進捗が、部隊ごとに開始→終了の順で流れること。"""
    from core.context import JobContext

    events = []
    ctx = JobContext(brief="イベント確認", options={"slide_count": 3},
                     on_event=events.append)
    Pipeline().run(ctx, only=["orchestrator", "planner"])

    kinds = [e["type"] for e in events]
    assert kinds[0] == "pipeline_start"
    assert kinds[-1] == "pipeline_end"
    assert kinds.count("agent_start") == 2
    assert kinds.count("agent_end") == 2
    assert all(e.get("message") for e in events if e["type"] == "agent_end")
