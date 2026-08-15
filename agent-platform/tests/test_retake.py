"""司令塔が不合格を出したら作り直すこと（自動リテイク）の確認。

「見つけて終わり」だと不良品がそのまま人の手に渡る。
指摘 → 作り直し → 再確認 が回ることをテストで固定しておく。
"""
from __future__ import annotations

from core.base_agent import BaseAgent, AgentResult
from core.context import JobContext
from core.pipeline import Pipeline, _revision_text


class _Maker(BaseAgent):
    key = "poster"
    name_ja = "掲示物制作"
    deliverable = "signage"
    use_tools = False

    def __init__(self):
        self.runs = 0
        self.revisions = []

    def _run(self, ctx):
        self.runs += 1
        self.revisions.append(ctx.options.get("revision", ""))
        ctx.state["signage"] = {"headline": "テスト"}
        return {"summary": "作りました（%d回目）" % self.runs}


class _Checker(BaseAgent):
    key = "acceptance"
    name_ja = "司令塔（最終確認）"
    use_tools = False

    def __init__(self, verdicts):
        self.verdicts = list(verdicts)
        self.runs = 0

    def _run(self, ctx):
        verdict = self.verdicts[min(self.runs, len(self.verdicts) - 1)]
        self.runs += 1
        return {"summary": "判定: %s" % verdict,
                "data": {"verdict": verdict, "gaps": ["文字が1文字だけ次行に落ちている"],
                         "fix_instructions": "折り返しを文節単位にする"}}


def test_failed_check_triggers_one_retake():
    maker, checker = _Maker(), _Checker(["needs_fix", "ok"])
    ctx = JobContext(brief="貼り紙を作って", options={})
    Pipeline(agents=[maker, checker]).run(ctx)

    assert maker.runs == 2, "指摘が出たのに作り直していない"
    assert checker.runs == 2, "作り直した後に再確認していない"
    assert "文字が1文字だけ" in maker.revisions[1], "指摘が制作側に渡っていない"


def test_retake_stops_at_the_limit():
    """何度直しても直らないとき、無限に回らないこと。"""
    maker, checker = _Maker(), _Checker(["failed"])
    ctx = JobContext(brief="貼り紙を作って", options={})
    Pipeline(agents=[maker, checker]).run(ctx)

    assert maker.runs == 2, "上限（既定1回）を超えて作り直している"


def test_ok_verdict_does_not_retake():
    maker, checker = _Maker(), _Checker(["ok"])
    ctx = JobContext(brief="貼り紙を作って", options={})
    Pipeline(agents=[maker, checker]).run(ctx)

    assert maker.runs == 1
    assert not maker.revisions[0], "合格なのに修正指示が入っている"


def test_revision_text_includes_gaps_and_fix():
    text = _revision_text({"gaps": ["余白が破綻", "文字が孤立"],
                           "fix_instructions": "文節で折る"})
    assert "余白が破綻" in text and "文字が孤立" in text
    assert "文節で折る" in text
