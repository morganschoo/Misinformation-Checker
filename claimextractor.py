"""Pulls out checkable factual claims from a social-media-style post.

This module wraps a call to Claude (via the anthropic package) and turns
the model's response into a plain Python list, the same pattern
analyzer.py uses -- prompt in, JSON out, parsed into something the rest
of the program can work with.

A "checkable" claim is one specific enough that a real source could
confirm or refute it (a named event, a statistic, a specific action by a
specific entity) -- as opposed to an opinion, a vague scare ("this common
item causes cancer" with no item named), or rhetorical framing. Posts
with no checkable claims are a normal, expected result, not an error.
"""

import json


class ExtractionError(Exception):
    """Raised when the extractor can't get or parse a usable result."""


class ClaimExtractor:
    """Uses an AI model to pull checkable factual claims out of a post."""

    def __init__(self, api_key=None, model="claude-sonnet-4-5", client=None):
        """Set up the Anthropic client.

        Same pattern as MisinfoAnalyzer in analyzer.py: if api_key isn't
        given, the anthropic package reads ANTHROPIC_API_KEY itself, and
        `client` lets tests inject a fake client instead of a real one.
        """
        self.model = model
        if client is not None:
            self.client = client
        else:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)

    def extract(self, post_text):
        """Pull checkable claims out of a single post.

        Returns a list of short strings, e.g.:
        ["NASA's James Webb telescope captured new images of Europa"]

        Returns an empty list if the post has no checkable claims (pure
        opinion, vague scare-mongering with nothing specific named,
        etc.) -- that's a normal result, not a failure.

        Raises ExtractionError if the API call fails or the model's
        reply can't be parsed into the expected shape.
        """
        prompt = self._build_prompt(post_text)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise ExtractionError(f"API call failed: {e}") from e

        raw_text = response.content[0].text
        return self._parse_response(raw_text)

    def _build_prompt(self, post_text):
        """Build the instruction we send to the model."""
        return (
            "You extract checkable factual claims from social media "
            "posts. A checkable claim is specific enough that a real "
            "source could confirm or refute it -- a named event, a "
            "statistic, a specific action by a specific entity. Do NOT "
            "extract opinions, rhetorical questions, or vague claims "
            "with nothing specific named (e.g. \"this common item "
            "causes cancer\" with no item named is NOT checkable).\n\n"
            "Respond ONLY with valid JSON in this exact shape, with no "
            "other text before or after it, and no markdown code "
            "fences (no ```):\n"
            '{"claims": [<short strings, one per checkable claim>]}\n\n'
            "Use an empty list if the post has no checkable claims.\n\n"
            f"Post:\n{post_text}"
        )

    def _parse_response(self, raw_text):
        """Turn the model's raw text reply into a validated list."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise ExtractionError(
                f"Model didn't return valid JSON: {raw_text[:200]!r}"
            ) from e

        if "claims" not in data or not isinstance(data["claims"], list):
            raise ExtractionError(f"Unexpected response shape: {data}")

        return data["claims"]
