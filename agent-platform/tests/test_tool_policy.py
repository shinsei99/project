"""司令塔が決めた「部隊ごとの道具のオン・オフ」が効いているかの確認。

道具を持たせると claude CLI 固定になり1回数十秒かかる。
依頼に応じて司令塔が切れることが速度の要になるので、テストで固定しておく。
"""
from __future__ import annotations

from agents.legal import LegalComplianceAgent
from agents.researcher import ResearcherAgent
from agents.reviewer import SpeedReviewerAgent


def test_class_defaults(ctx):
    """既定では、調査は道具あり・チェックは道具なし。"""
    assert ResearcherAgent().wants_tools is True
    assert LegalComplianceAgent().wants_tools is True
    assert SpeedReviewerAgent().wants_tools is False


def test_orchestrator_can_turn_tools_off(ctx):
    ctx.state["plan"] = {"agent_tools": {"researcher": ["none"]}}
    policy = ResearcherAgent().tool_policy(ctx)
    assert policy["any"] is False
    tools = ResearcherAgent().toolset(ctx)
    assert tools["web"] is False and tools["mcp"] is False


def test_orchestrator_can_turn_tools_on(ctx):
    """既定で道具を持たない部隊にも、司令塔が必要と判断すれば持たせられる。"""
    ctx.state["plan"] = {"agent_tools": {"reviewer": ["web", "browser"]}}
    agent = SpeedReviewerAgent()
    policy = agent.tool_policy(ctx)
    assert policy["any"] is True
    tools = agent.toolset(ctx)
    assert tools["web"] is True and tools["mcp"] is True


def test_partial_policy_only_affects_named_agents(ctx):
    """名指しされていない部隊はクラス既定のまま。"""
    ctx.state["plan"] = {"agent_tools": {"legal": ["none"]}}
    assert LegalComplianceAgent().tool_policy(ctx)["any"] is False
    assert ResearcherAgent().tool_policy(ctx) is None
    # 名指しされていない調査部隊はクラス既定のまま（Webあり・ブラウザは既定オフ）
    tools = ResearcherAgent().toolset(ctx)
    assert tools["web"] is True
    assert tools["mcp"] is False


def test_unknown_words_do_not_enable_everything(ctx):
    """想定外の語が来ても、道具を勝手に全部オンにしない。"""
    ctx.state["plan"] = {"agent_tools": {"legal": ["よくわからない道具"]}}
    policy = LegalComplianceAgent().tool_policy(ctx)
    assert policy["any"] is True          # 何か指定はされている
    assert policy["web"] is False         # ただし具体的な道具は付かない
    assert policy["mcp"] is False
