"""Generic thread-safe, JSON-backed set of words (kept lowercase).

Used as the storage backend for word pools that live *outside* the 5-level
familiarity process – e.g. the *ignore* list (names / proper nouns) and the
*mastered* list (words the learner already knows and never wants to study).
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Iterable


class WordSetStore:
    """Thread-safe JSON-backed set of words (kept lowercase)."""

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._words: set[str] = set()
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        # Accept either a bare list or {"words": [...]}.
        if isinstance(raw, dict):
            raw = raw.get("words", [])
        if isinstance(raw, list):
            self._words = {str(w).lower() for w in raw if str(w).strip()}

    def save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"words": sorted(self._words)}
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)

    # --------------------------------------------------------------- access
    def __contains__(self, word: str) -> bool:
        return word.lower() in self._words

    def contains(self, word: str) -> bool:
        return word.lower() in self._words

    def all(self) -> list[str]:
        return sorted(self._words)

    def add(self, word: str) -> bool:
        """Add ``word`` to the set. Returns True if newly added."""

        key = word.strip().lower()
        if not key:
            return False
        with self._lock:
            if key in self._words:
                return False
            self._words.add(key)
        self.save()
        return True

    def remove(self, word: str) -> bool:
        """Remove ``word`` from the set. Returns True if it was present."""

        key = word.strip().lower()
        with self._lock:
            if key not in self._words:
                return False
            self._words.discard(key)
        self.save()
        return True

    def keep(self, words: Iterable[str]) -> set[str]:
        """Return only the ``words`` that are *not* in the set (lowercased)."""

        return {w for w in words if w.lower() not in self._words}
