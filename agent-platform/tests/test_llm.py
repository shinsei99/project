"""LLM応答からのJSON取り出しと、プロバイダ未設定時のふるまい。"""
from __future__ import annotations

from core.llm import complete, extract_json


def test_extract_json_plain():
    assert extract_json('{"a": 1}') == {"a": 1}


def test_extract_json_with_fence_and_preamble():
    text = 'はい、こちらです。\n```json\n{"title": "案", "n": 2}\n```\nご確認ください。'
    assert extract_json(text) == {"title": "案", "n": 2}


def test_extract_json_with_trailing_prose():
    text = '{"slides": [{"no": 1}]} 以上が構成です。'
    assert extract_json(text) == {"slides": [{"no": 1}]}


def test_extract_json_ignores_braces_inside_strings():
    text = '説明します。{"note": "括弧 } を含む文字列", "ok": true}'
    assert extract_json(text) == {"note": "括弧 } を含む文字列", "ok": True}


def test_extract_json_returns_none_for_garbage():
    assert extract_json("JSONではありません") is None


def test_complete_reports_failure_when_no_provider():
    """キーが無い状態で例外を投げず ok=False を返すこと（縮退の前提）。"""
    result = complete("こんにちは", role="reasoning")
    assert result.ok is False
    assert result.error
