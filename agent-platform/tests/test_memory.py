"""部隊の学習（申し送り）の確認。

これが無いと、司令塔が見つけた不良を毎回忘れて同じ失敗を繰り返す。
「溜まる」「重複しない」「次のプロンプトに載る」の3点を固定する。
"""
from __future__ import annotations

import importlib

import pytest


@pytest.fixture
def memory(tmp_path, monkeypatch):
    """本物の知識ファイルを汚さないよう、一時フォルダに向ける。"""
    from core import memory as module

    importlib.reload(module)
    monkeypatch.setattr(module, "STORE", tmp_path / "lessons.json")
    monkeypatch.setattr(module, "READABLE", tmp_path / "lessons.md")
    return module


def test_records_and_reads_back(memory):
    added = memory.record("signage", ["原付が書かれていない"], "対象を全部書く")
    assert added == 1
    text = memory.describe_for_prompt("signage")
    assert "原付が書かれていない" in text
    assert "対象を全部書く" in text


def test_same_problem_is_counted_not_duplicated(memory):
    memory.record("signage", ["原付が書かれていない"])
    memory.record("signage", ["原付が、書かれていない。"])  # 表記ゆれ
    items = memory.lessons_for("signage", "failures")
    assert len(items) == 1, "同じ不良が重複して溜まっている"
    assert items[0]["count"] == 2
    assert "2回発生" in memory.describe_for_prompt("signage")


def test_records_successes_too(memory):
    """効いた点も覚えること（失敗だけ溜めると良い作り方が伝わらない）。"""
    memory.record_success("signage", ["撤去の流れを3段階の図で示した"])
    text = memory.describe_for_prompt("signage")
    assert "これまで効いた作り方" in text
    assert "撤去の流れを3段階の図で示した" in text


def test_successes_and_failures_are_separate(memory):
    memory.record("signage", ["原付が抜けている"])
    memory.record_success("signage", ["段階図が効いた"])
    text = memory.describe_for_prompt("signage")
    assert text.index("効いた作り方") < text.index("指摘された不良"), \
        "効いた作り方を先に見せる（否定から入らない）"
    assert len(memory.lessons_for("signage", "failures")) == 1
    assert len(memory.lessons_for("signage", "successes")) == 1


def test_frequent_problems_come_first(memory):
    memory.record("signage", ["たまにある不良"])
    for _ in range(3):
        memory.record("signage", ["よく起きる不良"])
    items = memory.lessons_for("signage", "failures")
    assert items[0]["text"] == "よく起きる不良"


def test_genres_do_not_leak_into_each_other(memory):
    memory.record("signage", ["掲示物の不良"])
    memory.record("promo", ["チラシの不良"])
    assert "掲示物の不良" not in memory.describe_for_prompt("promo")
    assert "チラシの不良" not in memory.describe_for_prompt("signage")


def test_common_lessons_apply_to_every_genre(memory):
    memory.record("共通", ["どの成果物でも起きる不良"])
    assert "どの成果物でも起きる不良" in memory.describe_for_prompt("signage")


def test_empty_memory_adds_nothing_to_prompt(memory):
    assert memory.describe_for_prompt("signage") == ""


def test_readable_file_is_written(memory):
    memory.record("signage", ["原付が書かれていない"], "対象を全部書く")
    text = memory.READABLE.read_text(encoding="utf-8")
    assert "申し送り" in text and "原付が書かれていない" in text
