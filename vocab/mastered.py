"""Persistent set of words the learner has already mastered.

Mastered words are ones the learner knows well enough that they never need to
appear in the 5-level familiarity process again.  Like the ignore list they are
filtered out of the whole pipeline: they are not highlighted while reading,
never show up in the glossary, and are skipped in the flashcard study queue.

The one way back in is to click the word again while reading (*read & mark*),
which pulls it out of this list and back into the normal learning pool.

The list is stored as a small JSON file (``data/mastered.json``) so the choice
survives restarts and applies to every future upload.
"""

from __future__ import annotations

from pathlib import Path

from .wordset import WordSetStore

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASTERED_FILE = PROJECT_ROOT / "data" / "mastered.json"


class MasteredStore(WordSetStore):
    """JSON-backed set of mastered words (``data/mastered.json``)."""

    def __init__(self, path: Path | str = DEFAULT_MASTERED_FILE) -> None:
        super().__init__(path)
