"""Persistent, alphabetically sharded set of mastered words.

Mastered words are ones the learner knows well enough that they never need to
appear in the 5-level familiarity process again.  Like the ignore list they are
filtered out of the whole pipeline: they are not highlighted while reading,
never show up in the glossary, and are skipped in the flashcard study queue.

The one way back in is to click the word again while reading (*read & mark*),
which pulls it out of this list and back into the normal learning pool.

The list is stored under ``data/mastered/`` in ``a.json`` through ``z.json``.
Only the shard affected by an add/remove operation is rewritten.  Words that
do not begin with an ASCII letter live in ``_other.json``.  The legacy
``data/mastered.json`` file is migrated automatically on first startup.
"""

from __future__ import annotations

import json
import string
import threading
from pathlib import Path
from typing import Iterable

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MASTERED_DIR = PROJECT_ROOT / "data" / "mastered"
LEGACY_MASTERED_FILE = PROJECT_ROOT / "data" / "mastered.json"
SHARDS = tuple(string.ascii_lowercase)


class MasteredStore:
    """Thread-safe mastered set backed by per-initial JSON shards."""

    def __init__(
        self,
        path: Path | str = DEFAULT_MASTERED_DIR,
        legacy_path: Path | str | None = None,
    ) -> None:
        supplied = Path(path)
        # Preserve compatibility with callers that used to pass mastered.json.
        self._dir = supplied.parent / "mastered" if supplied.suffix else supplied
        self._legacy_path = Path(legacy_path) if legacy_path else (
            supplied if supplied.suffix else self._dir.parent / "mastered.json"
        )
        self._lock = threading.Lock()
        self._words: set[str] = set()
        self._load_or_migrate()

    @staticmethod
    def _shard(word: str) -> str:
        initial = word[:1].lower()
        return initial if initial in SHARDS else "_other"

    def _shard_path(self, shard: str) -> Path:
        return self._dir / f"{shard}.json"

    @staticmethod
    def _read_words(path: Path) -> set[str]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return set()
        if isinstance(raw, dict):
            raw = raw.get("words", [])
        if not isinstance(raw, list):
            return set()
        return {str(word).strip().lower() for word in raw if str(word).strip()}

    def _load_or_migrate(self) -> None:
        shard_paths = [self._shard_path(shard) for shard in (*SHARDS, "_other")]
        if any(path.exists() for path in shard_paths):
            for path in shard_paths:
                self._words.update(self._read_words(path))
            return

        self._words = self._read_words(self._legacy_path)
        self._dir.mkdir(parents=True, exist_ok=True)
        # Create every A-Z shard during migration, including empty ones, so the
        # directory layout is predictable and the legacy file is ignored later.
        for shard in (*SHARDS, "_other"):
            self._save_shard(shard)

    def _save_shard(self, shard: str) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        path = self._shard_path(shard)
        payload = {"words": sorted(w for w in self._words if self._shard(w) == shard)}
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)

    def __contains__(self, word: str) -> bool:
        return word.lower() in self._words

    def contains(self, word: str) -> bool:
        return word.lower() in self._words

    def all(self) -> list[str]:
        return sorted(self._words)

    def add(self, word: str) -> bool:
        key = word.strip().lower()
        if not key:
            return False
        with self._lock:
            if key in self._words:
                return False
            self._words.add(key)
            self._save_shard(self._shard(key))
        return True

    def remove(self, word: str) -> bool:
        key = word.strip().lower()
        with self._lock:
            if key not in self._words:
                return False
            self._words.remove(key)
            self._save_shard(self._shard(key))
        return True

    def keep(self, words: Iterable[str]) -> set[str]:
        return {word for word in words if word.lower() not in self._words}
