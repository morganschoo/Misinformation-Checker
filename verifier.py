"""Verifies a single checkable claim against real sources.

Same wrap-a-Claude-call-and-parse-JSON pattern as analyzer.py and
claimextractor.py, but this one gives Claude the built-in `web_search`
tool so it can actually look things up instead of guessing from
training data. Anthropic runs the search server-side and hands results
back within the same API call -- there's no manual tool-loop to write.

The verdict is always one of three honest outcomes:
  - "supported"    -- at least two independent sources corroborate it
  - "contradicted" -- a credible source directly refutes it
  - "unverified"   -- search didn't turn up enough to say either way

"unverified" is a normal, expected result -- it means the tool is being
honest about the limits of what it found, not that something broke.
"""

import json


class VerificationError(Exception):
    """Raised when the verifier can't get or parse a usable result."""


class ClaimVerifier:
    """Uses web search + an AI model to check a single claim's veracity."""

    def __init__(self, api_key=None, model="claude-sonnet-4-5", client=None,
                 max_searches=3):
        """Set up the Anthropic client.

        Same pattern as MisinfoAnalyzer/ClaimExtractor: if api_key isn't
        given, the anthropic package reads ANTHROPIC_API_KEY itself, and
        `client` lets tests inject a fake client instead of a real one.

        `model` must support the web_search tool (Claude 4.6+).
        `max_searches` caps how many searches the model can run for one
        claim -- keeps cost/latency bounded.
        """
        self.model = model
        self.max_searches = max_searches
        if client is not None:
            self.client = client
        else:
            import anthropic
            self.client = anthropic.Anthropic(api_key=api_key)

    def verify(self, claim):
        """Check a single claim against sources found via web search.

        Returns a dict like:
        {
            "verdict": "supported",
            "explanation": "Confirmed by NASA's own press release and...",
            "sources": [{"url": "...", "title": "..."}],
        }

        Raises VerificationError only if the API call itself fails or
        the reply can't be parsed at all -- a claim search that simply
        doesn't find enough evidence comes back as a normal
        verdict="unverified" result, not an exception.
        """
        prompt = self._build_prompt(claim)

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                tools=[{
                    "type": "web_search_20260318",
                    "name": "web_search",
                    "max_uses": self.max_searches,
                }],
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as e:
            raise VerificationError(f"API call failed: {e}") from e

        # Unlike analyzer.py/claimextractor.py, the response isn't a
        # single text block: with a tool available, Claude's reply can
        # include search-call blocks and search-result blocks before
        # its final write-up. We want the LAST block that has text --
        # that's where the final JSON verdict lives.
        text_blocks = [b.text for b in response.content if hasattr(b, "text") and b.text]
        if not text_blocks:
            raise VerificationError(
                f"Model reply had no text content: {response.content!r}"
            )
        raw_text = text_blocks[-1]

        return self._parse_response(raw_text)

    def verify_all(self, claims):
        """Convenience helper: verify a list of claim strings, returning
        a list of dicts each shaped like {"claim": ..., "verdict": ...,
        "explanation": ..., "sources": [...]}.

        A claim that fails with VerificationError is still included, as
        an "unverified" result carrying the error -- so one bad claim
        doesn't stop the rest of the post's claims (or the rest of
        main.py's run) from being processed.
        """
        results = []
        for claim in claims:
            try:
                verdict = self.verify(claim)
            except VerificationError as e:
                verdict = {"verdict": "unverified", "explanation": str(e), "sources": []}
            results.append({"claim": claim, **verdict})
        return results

    def _build_prompt(self, claim):
        """Build the instruction we send to the model."""
        return (
            "You are fact-checking a single claim pulled from a social "
            "media post. Use web search to find independent sources "
            "that either support or contradict it.\n\n"
            f'Claim: "{claim}"\n\n'
            "Rules:\n"
            "- Only mark it \"supported\" if at least TWO independent, "
            "credible sources corroborate it.\n"
            "- Mark it \"contradicted\" if a credible source directly "
            "refutes it or gives materially different facts.\n"
            "- If search doesn't turn up enough to confidently say "
            "either way -- including if the claim is too recent, too "
            "obscure, or you only find sources repeating the same "
            "original post -- mark it \"unverified\". Do not guess "
            "based on what seems plausible; only use sources you "
            "actually found via search this turn.\n\n"
            "After searching, respond with ONLY a final JSON object (no "
            "other text after it, no markdown code fences), in this "
            "exact shape:\n"
            '{"verdict": "supported" | "contradicted" | "unverified", '
            '"explanation": "<one or two sentences>", '
            '"sources": [{"url": "<url>", "title": "<title>"}]}'
        )

    def _parse_response(self, raw_text):
        """Turn the model's raw text reply into a validated dict."""
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`").strip()
            if cleaned.lower().startswith("json"):
                cleaned = cleaned[4:].strip()

        # The model may have written a sentence or two of reasoning
        # before the JSON despite instructions -- grab the outermost
        # {...} block rather than assuming the whole string is JSON.
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end == -1 or end < start:
            raise VerificationError(
                f"Model didn't return valid JSON: {raw_text[:200]!r}"
            )

        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as e:
            raise VerificationError(
                f"Model didn't return valid JSON: {raw_text[:200]!r}"
            ) from e

        if data.get("verdict") not in ("supported", "contradicted", "unverified"):
            raise VerificationError(f"Unexpected response shape: {data}")

        data.setdefault("explanation", "")
        data.setdefault("sources", [])
        return data
