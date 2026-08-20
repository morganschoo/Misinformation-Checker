"""Core logic for scoring social-media-style posts for misinformation risk.

This module wraps a call to Claude (via the anthropic package) and turns
the model's response into a plain Python dictionary your program can work
with, the same way pathlib and json did for files in Chapter 10.
"""

import json


class AnalysisError(Exception):
    """Raised when the analyzer can't get or parse a usable result."""


class MisinfoAnalyzer:
    """Uses an AI model to score a single post for misinformation risk."""

    def __init__(self, api_key=None, model="claude-sonnet-4-5", client=None):
        """Set up the Anthropic client.

        If api_key isn't given, the anthropic package automatically reads
        the ANTHROPIC_API_KEY environment variable instead.

        `client` lets tests (or other code) inject a fake client instead
        of a real anthropic.Anthropic() instance -- see test_analyzer.py.
        The anthropic package is only imported here, lazily, so this
        module can still be imported/tested even if that package isn't
        installed yet.
        """
        self.model = model
        if client is not None:
            self.client = client
        else:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)

    def analyze(self, post_text):
        """Score a single post for misinformation risk.

        Returns a dict like:
        {
            "score": 82,
            "flags": ["unverified claim", "emotional language"],
            "reasoning": "No source cited and uses alarmist language.",
        }

        Raises AnalysisError if the API call fails or the model's reply
        can't be parsed into the expected shape.
        """
        prompt = self._build_prompt(post_text)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=300,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise AnalysisError(f"API call failed: {e}") from e

        raw_text = response.content[0].text
        return self._parse_response(raw_text)

    def _build_prompt(self, post_text):
        """Build the instruction we send to the model."""
        return (
            "You are a misinformation-risk classifier. Analyze the "
            "following social media post and respond ONLY with valid "
            "JSON in this exact shape, with no other text before or "
            "after it:\n"
            '{"score": <integer 0-100>, "flags": [<short strings>], '
            '"reasoning": "<one or two sentences>"}\n\n'
            "score: 0 means clearly reliable, 100 means highly likely "
            "misinformation.\n"
            "flags: short labels for warning signs you noticed, for "
            'example "unverified claim", "emotional language", '
            '"no source", "impersonation", "out-of-context image", '
            '"conspiracy framing". Use an empty list if you see none.\n\n'
            f"Post:\n{post_text}"
        )

    def _parse_response(self, raw_text):
        """Turn the model's raw text reply into a validated dict."""
        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as e:
            raise AnalysisError(
                f"Model didn't return valid JSON: {raw_text[:200]!r}"
            ) from e

        if "score" not in data or "flags" not in data:
            raise AnalysisError(f"Unexpected response shape: {data}")

        return data
