"""Saving and loading analysis results, using the same json + pathlib
pattern from Chapter 10.
"""

import json
from pathlib import Path


def save_results(results, path):
    """Write a list of result dicts to a JSON file."""
    path = Path(path)
    path.write_text(json.dumps(results, indent=2), encoding="utf-8")


def load_results(path):
    """Read previously saved results back into memory.

    Returns an empty list if the file doesn't exist yet.
    """
    path = Path(path)
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))
