"""個々の部隊が、入力が欠けていても落ちないことを確認する。"""
from __future__ import annotations

from pathlib import Path

import pytest

from agents.legal import LegalComplianceAgent
from agents.orchestrator import OrchestratorAgent
from agents.planner import PresentationPlannerAgent
from agents.reviewer import SpeedReviewerAgent
from agents.voice import VoiceAgent


def _deck(ctx, narration="これはテスト用のナレーションです。"):
    ctx.state["plan"] = {"title": "テスト企画", "slide_count": 2}
    ctx.state["deck"] = {
        "title": "テスト企画", "subtitle": "",
        "slides": [
            {"no": 1, "title": "はじめに", "bullets": ["要点A"],
             "narration": narration, "image_prompt": "abstract"},
            {"no": 2, "title": "まとめ", "bullets": ["要点B"],
             "narration": narration, "image_prompt": "abstract"},
        ],
    }


def test_orchestrator_falls_back_without_llm(ctx):
    result = OrchestratorAgent().run(ctx)
    assert result.ok and result.degraded
    assert ctx.state["plan"]["slide_count"] == 3


def test_planner_produces_requested_slide_count(ctx):
    ctx.state["plan"] = {"title": "テスト", "slide_count": 5}
    result = PresentationPlannerAgent().run(ctx)
    assert result.ok
    assert len(ctx.state["deck"]["slides"]) == 5
    assert all(s["narration"] for s in ctx.state["deck"]["slides"])


def test_agents_do_not_crash_without_deck(ctx):
    """前工程が飛んでいても例外にせず、その旨を返すこと。"""
    for agent in (SpeedReviewerAgent(), LegalComplianceAgent(), VoiceAgent()):
        result = agent.run(ctx)
        assert result.ok, result.error
        assert result.degraded


def test_reviewer_catches_mechanical_problems(ctx):
    _deck(ctx, narration="")
    ctx.state["deck"]["slides"][1]["bullets"] = []
    result = SpeedReviewerAgent().run(ctx)
    messages = [i["message"] for i in ctx.state["review"]["issues"]]
    assert any("ナレーションが空" in m for m in messages)
    assert any("箇条書きがありません" in m for m in messages)
    assert ctx.state["review"]["major"] >= 2


def test_legal_flags_forbidden_expressions(ctx):
    _deck(ctx)
    ctx.state["deck"]["slides"][0]["bullets"] = ["必ず儲かる投資です", "業界No.1の実績"]
    LegalComplianceAgent().run(ctx)
    audit = ctx.state["legal"]
    assert audit["critical_count"] >= 1
    assert any("最上級表現" in r["law"] for r in audit["risks"])


def test_voice_creates_files_even_without_tts(ctx):
    _deck(ctx)
    result = VoiceAgent().run(ctx)
    assert result.ok
    records = ctx.state["audio"]
    assert len(records) == 2
    for record in records:
        path = Path(ctx.root) / record["path"]
        assert path.exists() and path.stat().st_size > 0
        assert record["seconds"] >= 2.0


def test_image_agent_prefers_uploaded_files(ctx):
    pytest.importorskip("PIL")
    from PIL import Image

    from agents.image_generator import ImageGeneratorAgent

    _deck(ctx)
    sample = ctx.dir("input") / "sample.png"
    Image.new("RGB", (64, 64), (200, 30, 30)).save(sample)

    ImageGeneratorAgent().run(ctx)
    records = ctx.state["images"]
    assert records[0]["backend"] == "uploaded"
    assert records[1]["backend"] == "stub"
    for record in records:
        assert (Path(ctx.root) / record["path"]).stat().st_size > 0
