"""Tests for MisinfoAnalyzer.

These don't hit the real API -- they fake the Anthropic client's
response so tests run offline, free, and fast (same idea as Chapter 11:
test the logic, not the network).
"""

import json

import pytest

from analyzer import AnalysisError, MisinfoAnalyzer


class FakeContent:
    """Stands in for one block of a real API response's content list."""

    def __init__(self, text):
        self.text = text


class FakeResponse:
    """Stands in for the object anthropic's messages.create() returns."""

    def __init__(self, text):
        self.content = [FakeContent(text)]


class FakeMessages:
    def __init__(self, reply_text):
        self._reply_text = reply_text

    def create(self, **kwargs):
        return FakeResponse(self._reply_text)


class FakeClient:
    """Stands in for anthropic.Anthropic() so no real network call happens."""

    def __init__(self, reply_text):
        self.messages = FakeMessages(reply_text)


@pytest.fixture
def good_reply():
    return json.dumps({
        "score": 82,
        "flags": ["unverified claim", "emotional language"],
        "reasoning": "No source cited and uses alarmist language.",
    })


def test_analyze_returns_parsed_result(good_reply):
    analyzer = MisinfoAnalyzer(client=FakeClient(good_reply))

    result = analyzer.analyze("Some post text")

    assert result["score"] == 82
    assert "unverified claim" in result["flags"]


def test_analyze_raises_on_bad_json():
    analyzer = MisinfoAnalyzer(client=FakeClient("not json at all"))

    with pytest.raises(AnalysisError):
        analyzer.analyze("Some post text")


def test_analyze_raises_on_missing_fields():
    reply = json.dumps({"reasoning": "missing score/flags"})
    analyzer = MisinfoAnalyzer(client=FakeClient(reply))

    with pytest.raises(AnalysisError):
        analyzer.analyze("Some post text")
