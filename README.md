# misinfo_checker

A command-line tool that scores social-media-style posts for
misinformation risk using Claude, extracts and verifies checkable
factual claims against real web sources, and saves the results as
JSON.

## How it's built (mapped to what you've already learned)

- `analyzer.py` — a **class** (`MisinfoAnalyzer`) that builds a prompt,
  calls the API, and parses the JSON reply. Uses **try/except** to turn
  API or parsing failures into a clear `AnalysisError` instead of a crash.
- `claimextractor.py` — a **class** (`ClaimExtractor`) that pulls
  specific, checkable factual claims out of a post (skipping opinions
  and vague scare-mongering with nothing named). Same prompt-in/JSON-out
  pattern as `analyzer.py`.
- `verifier.py` — a **class** (`ClaimVerifier`) that checks each claim
  using Claude's built-in `web_search` tool, and returns an honest
  verdict: `"supported"` (2+ independent sources agree), `"contradicted"`
  (a credible source refutes it), or `"unverified"` (search didn't turn
  up enough either way — a normal result, not a failure).
- `storage.py` — **file I/O** with `pathlib` + `json`, same pattern as
  Chapter 10.
- `main.py` — the **CLI**: reads a text file of posts, loops through
  them calling the analyzer, extractor, and verifier in turn (Chapter 8
  functions + Chapter 17 API pattern), and saves results.
- `test_analyzer.py` / `test_claimextractor.py` / `test_verifier.py` —
  **pytest** tests (Chapter 11) that fake the API client so tests run
  offline, free, and fast, and check the parsing logic handles both
  good and bad responses correctly.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Get an API key from the Anthropic Console, then rename
   `env.example.txt` to `.env` and paste your key into it:
   ```
   ANTHROPIC_API_KEY=sk-ant-your-real-key-here
   ```
   (Windows sometimes mangles filenames starting with a dot when
   downloaded — if `.env.example` looks odd, just create a plain new
   file called `.env` yourself and put that one line in it.)
3. Run the tests (no API key needed — they use a fake client):
   ```
   pytest
   ```

Note: verification uses the `web_search` tool, which requires a model
that supports it (Claude 4.6+) and costs a small amount per search on
top of normal token usage — see the Anthropic Console for current
pricing. Use `--no-verify` (below) while you're just iterating on the
scoring prompt, to avoid burning search calls.

## Usage

```
python main.py sample_posts.txt
```

Optional flags:

```
python main.py sample_posts.txt -o results.json -t 70
python main.py sample_posts.txt --no-verify
```

- `-o / --output` — where to save results (default `results.json`)
- `-t / --threshold` — score at/above which a post is flagged (default 60)
- `--no-verify` — skip claim extraction/verification and just score
  posts (faster, no web-search calls)

Each line in the input file is treated as one post. The tool prints a
running summary as it works and writes full results to the output JSON
file: score, flags, reasoning, the original post, flagged true/false,
and a `claims` list with each checkable claim's verdict, explanation,
and sources.

## Before you push to GitHub

Your `.env` file will contain your real API key. Make sure this folder
has a `.gitignore` file containing at least:

```
.env
__pycache__/
*.pyc
results.json
venv/
```

`.env.example` / `env.example.txt` (no real key) is fine to commit —
`.env` (your real key) is not.

## What's next

Some natural next steps, roughly in order of how useful they are:

1. **Try it for real.** Run it against `sample_posts.txt`, then write
   your own test posts — including tricky/ambiguous ones — and see how
   the model scores them and which claims come back unverified.
2. **Tune the prompts.** `_build_prompt()` in `analyzer.py`,
   `claimextractor.py`, and `verifier.py` are the "brain" of this tool
   — adjust what counts as a flag or a checkable claim, and watch for
   cases where verification is too eager to say "supported" on thin
   evidence.
3. **Swap in a real database.** `results.json` works for now, but a
   `sqlite3` table would let you query "show me everything flagged this
   week" without loading the whole file.
4. **Batch input from somewhere real.** Instead of a hand-written text
   file, pull posts from an RSS feed, a CSV export, or an API (you
   already know how — see Chapter 16/17 patterns) and feed them in.
5. **Add a simple web UI later**, only if you want one — `FastAPI` is a
   lighter-weight fit for this than Django.
