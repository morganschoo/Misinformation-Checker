"""CLI entry point: score every post in a text file for misinformation
risk and save the results.

Usage:
    python main.py sample_posts.txt
    python main.py sample_posts.txt -o results.json -t 70
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

from analyzer import AnalysisError, MisinfoAnalyzer
from storage import save_results

# Loads ANTHROPIC_API_KEY from a .env file in this folder, if present.
load_dotenv()


def load_posts(path):
    """Read posts from a text file, one post per line (blanks skipped)."""
    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines()]
    return [line for line in lines if line]


def parse_args():
    parser = argparse.ArgumentParser(
        description="Score social-media-style posts for misinformation risk."
    )
    parser.add_argument(
        "input_file", type=Path, help="Text file with one post per line"
    )
    parser.add_argument(
        "-o", "--output", type=Path, default=Path("results.json"),
        help="Where to save results as JSON (default: results.json)",
    )
    parser.add_argument(
        "-t", "--threshold", type=int, default=60,
        help="Score at/above which a post is flagged (default: 60)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if not args.input_file.exists():
        print(f"Error: {args.input_file} not found.")
        sys.exit(1)

    posts = load_posts(args.input_file)
    if not posts:
        print("No posts found in input file.")
        sys.exit(1)

    analyzer = MisinfoAnalyzer()
    results = []

    for i, post in enumerate(posts, start=1):
        print(f"\n[{i}/{len(posts)}] Analyzing: {post[:60]}...")
        try:
            result = analyzer.analyze(post)
        except AnalysisError as e:
            print(f"  Skipped (error): {e}")
            continue

        result["post"] = post
        result["flagged"] = result["score"] >= args.threshold
        results.append(result)

        marker = "FLAGGED" if result["flagged"] else "ok"
        print(f"  Score: {result['score']} [{marker}] - "
              f"{result.get('reasoning', '')}")

    save_results(results, args.output)
    flagged_count = sum(1 for r in results if r["flagged"])
    print(f"\nDone. {flagged_count}/{len(results)} posts flagged. "
          f"Results saved to {args.output}")


if __name__ == "__main__":
    main()
