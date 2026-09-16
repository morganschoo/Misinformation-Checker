"""Tests for ClaimExtractor.

Same idea as test_analyzer.py: fake the Anthropic client's response so
tests run offline, free, and fast, and check the parsing logic handles
good responses, empty-claims responses, and bad ones correctly.
"""

import json

import pytest

from claimextractor import ClaimExtractor, ExtractionError


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


def test_extract_returns_parsed_claims():
    reply = json.dumps({
        "claims": ["NASA's James Webb telescope captured new images of Europa"],
    })
    extractor = ClaimExtractor(client=FakeClient(reply))

    claims = extractor.extract("NASA announced today that...")

    assert claims == ["NASA's James Webb telescope captured new images of Europa"]


def test_extract_returns_empty_list_for_no_checkable_claims():
    reply = json.dumps({"claims": []})
    extractor = ClaimExtractor(client=FakeClient(reply))

    claims = extractor.extract("This is just my opinion, nothing checkable here.")

    assert claims == []


def test_extract_raises_on_bad_json():
    extractor = ClaimExtractor(client=FakeClient("not json at all"))

    with pytest.raises(ExtractionError):
        extractor.extract("Some post text")


def test_extract_raises_on_missing_claims_field():
    reply = json.dumps({"reasoning": "forgot the claims field"})
    extractor = ClaimExtractor(client=FakeClient(reply))

    with pytest.raises(ExtractionError):
        extractor.extract("Some post text")
