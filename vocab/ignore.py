"""Persistent set of words the learner chooses to ignore.

Ignored words are things the learner never needs to memorise – proper nouns,
personal names, brand names, etc.  They are filtered out of the whole pipeline:
uploaded text is not registered for them, they are not highlighted while
reading, they never show up in the glossary, and they are removed from the
familiarity buckets in *My Words*.

The list is stored as a small JSON file (``data/ignore.json``) so the choice
survives restarts and applies to every future upload.
"""

from __future__ import annotations

from pathlib import Path

from .wordset import WordSetStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_IGNORE_FILE = PROJECT_ROOT / "data" / "ignore.json"


class IgnoreStore(WordSetStore):
    """JSON-backed set of ignored words (``data/ignore.json``)."""

    def __init__(self, path: Path | str = DEFAULT_IGNORE_FILE) -> None:
        super().__init__(path)
