"""Tests for ClaimVerifier.

Same fake-the-client idea as test_analyzer.py / test_claimextractor.py.
Also covers the one thing that's different about this module: a real
web-search response can carry several content blocks (search calls,
search results, final write-up) before the text we actually want, so
FakeResponse here supports multiple blocks to check we grab the LAST
one with text on it.
"""

import json

import pytest

from verifier import ClaimVerifier, VerificationError


class FakeContent:
    """Stands in for one block of a real API response's content list.
    Deliberately has no `type` attribute -- a real server_tool_use block
    wouldn't have `.text` either, which is exactly why the verifier
    checks `hasattr(b, "text")` rather than relying on a `type` field."""

    def __init__(self, text):
        self.text = text


class FakeResponse:
    """Stands in for the object anthropic's messages.create() returns.
    Accepts one or more text blocks, simulating a multi-step search
    response."""

    def __init__(self, *texts):
        self.content = [FakeContent(t) for t in texts]


class FakeMessages:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


class FakeClient:
    """Stands in for anthropic.Anthropic() so no real network call happens."""

    def __init__(self, response):
        self.messages = FakeMessages(response)


def _verdict_json(**overrides):
    data = {
        "verdict": "supported",
        "explanation": "Confirmed by two independent sources.",
        "sources": [{"url": "https://example.com", "title": "Example"}],
    }
    data.update(overrides)
    return json.dumps(data)


def test_verify_returns_parsed_verdict():
    response = FakeResponse(_verdict_json())
    verifier = ClaimVerifier(client=FakeClient(response))

    result = verifier.verify("Some claim")

    assert result["verdict"] == "supported"
    assert result["sources"][0]["url"] == "https://example.com"


def test_verify_uses_last_text_block_after_search_steps():
    # Simulates Claude narrating a search ("Let me look that up...") in
    # an earlier block before the real verdict JSON in the last one.
    response = FakeResponse("Let me search for this claim...", _verdict_json(verdict="unverified"))
    verifier = ClaimVerifier(client=FakeClient(response))

    result = verifier.verify("Some obscure claim")

    assert result["verdict"] == "unverified"


def test_verify_raises_on_bad_json():
    response = FakeResponse("not json at all")
    verifier = ClaimVerifier(client=FakeClient(response))

    with pytest.raises(VerificationError):
        verifier.verify("Some claim")


def test_verify_raises_on_invalid_verdict_value():
    response = FakeResponse(_verdict_json(verdict="probably true"))
    verifier = ClaimVerifier(client=FakeClient(response))

    with pytest.raises(VerificationError):
        verifier.verify("Some claim")


def test_verify_all_downgrades_failures_to_unverified():
    response = FakeResponse("not json at all")
    verifier = ClaimVerifier(client=FakeClient(response))

    results = verifier.verify_all(["claim one"])

    assert results[0]["claim"] == "claim one"
    assert results[0]["verdict"] == "unverified"
