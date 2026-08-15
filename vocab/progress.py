"""Per-learner familiarity tracking, persisted to a JSON file.

Every word has a :class:`~vocab.models.Familiarity` level from 1 (陌生
/ unfamiliar) to 5 (掌握 / mastered).  Words the learner has never touched are
treated as :data:`~vocab.models.Familiarity.UNFAMILIAR` by default, so the
whole vocabulary is always categorised across the 5 levels.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Familiarity

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PROGRESS_FILE = PROJECT_ROOT / "data" / "progress.json"

# How a study answer changes the familiarity level.
#   "again"  – did not know it        -> drop back towards Unfamiliar
#   "hard"   – recalled with effort   -> nudge up one
#   "good"   – recalled correctly     -> up one
#   "easy"   – instantly known        -> jump to Mastered
_RESPONSES = {"again", "hard", "good", "easy"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class WordProgress:
    familiarity: int = int(Familiarity.UNFAMILIAR)
    seen: int = 0
    correct: int = 0
    wrong: int = 0
    updated: str = field(default_factory=_now)

    def to_dict(self) -> dict:
        return {
            "familiarity": self.familiarity,
            "seen": self.seen,
            "correct": self.correct,
            "wrong": self.wrong,
            "updated": self.updated,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WordProgress":
        return cls(
            familiarity=int(data.get("familiarity", Familiarity.UNFAMILIAR)),
            seen=int(data.get("seen", 0)),
            correct=int(data.get("correct", 0)),
            wrong=int(data.get("wrong", 0)),
            updated=str(data.get("updated", _now())),
        )


class ProgressStore:
    """Thread-safe JSON-backed store of per-word familiarity."""

    def __init__(self, path: Path | str = DEFAULT_PROGRESS_FILE) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, WordProgress] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        self._data = {
            word.lower(): WordProgress.from_dict(value)
            for word, value in raw.items()
        }

    def save(self) -> None:
        with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            payload = {word: prog.to_dict() for word, prog in self._data.items()}
            tmp = self._path.with_suffix(self._path.suffix + ".tmp")
            tmp.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            tmp.replace(self._path)

    # --------------------------------------------------------------- access
    def familiarity(self, word: str) -> Familiarity:
        prog = self._data.get(word.lower())
        level = prog.familiarity if prog else int(Familiarity.UNFAMILIAR)
        return Familiarity(_clamp(level))

    def get(self, word: str) -> WordProgress | None:
        return self._data.get(word.lower())

    def set_familiarity(self, word: str, level: int) -> Familiarity:
        level = _clamp(level)
        with self._lock:
            prog = self._data.setdefault(word.lower(), WordProgress())
            prog.familiarity = level
            prog.updated = _now()
        self.save()
        return Familiarity(level)

    def register_words(
        self, words: Iterable[str], level: int = int(Familiarity.UNFAMILIAR)
    ) -> int:
        """Add tracking entries for ``words`` not seen before.

        Words already present keep their current familiarity untouched; brand
        new words are recorded at ``level`` (default: Unfamiliar). Returns the
        number of newly added words.
        """

        level = _clamp(level)
        added = 0
        with self._lock:
            for word in words:
                key = word.lower()
                if key and key not in self._data:
                    self._data[key] = WordProgress(familiarity=level)
                    added += 1
        if added:
            self.save()
        return added

    def remove(self, word: str) -> bool:
        """Delete a word's tracking entry entirely. Returns True if removed."""

        key = word.lower()
        with self._lock:
            removed = self._data.pop(key, None) is not None
        if removed:
            self.save()
        return removed

    def remove_many(self, words: Iterable[str]) -> int:
        """Delete multiple tracking entries and persist once."""

        keys = {word.lower() for word in words if word}
        with self._lock:
            removed = sum(self._data.pop(key, None) is not None for key in keys)
        if removed:
            self.save()
        return removed

    def record(self, word: str, response: str) -> Familiarity:
        """Update familiarity from a study ``response`` and persist.

        ``response`` is one of ``again`` / ``hard`` / ``good`` / ``easy``.
        """

        if response not in _RESPONSES:
            raise ValueError(f"unknown response: {response!r}")

        with self._lock:
            prog = self._data.setdefault(word.lower(), WordProgress())
            prog.seen += 1
            current = prog.familiarity

            if response == "again":
                new = max(int(Familiarity.UNFAMILIAR), current - 1)
                prog.wrong += 1
            elif response == "hard":
                new = _clamp(current + 1)
                prog.correct += 1
            elif response == "good":
                new = _clamp(current + 1)
                prog.correct += 1
            else:  # easy
                new = int(Familiarity.MASTERED)
                prog.correct += 1

            # First correct sighting of a brand-new word should at least reach
            # "learning" so it leaves the Unfamiliar bucket.
            if response != "again" and new <= int(Familiarity.UNFAMILIAR):
                new = int(Familiarity.LEARNING)

            prog.familiarity = new
            prog.updated = _now()

        self.save()
        return Familiarity(prog.familiarity)

    # ------------------------------------------------------------ analytics
    def counts(self, vocabulary: list[str] | set[str] | None = None) -> dict[int, int]:
        """Count words per familiarity level.

        If ``vocabulary`` is given, words never studied are counted as
        Unfamiliar so every word in the vocabulary is represented.
        """

        counts = {int(level): 0 for level in Familiarity}
        if vocabulary is not None:
            seen = set()
            for word in vocabulary:
                counts[int(self.familiarity(word))] += 1
                seen.add(word.lower())
        else:
            for prog in self._data.values():
                counts[_clamp(prog.familiarity)] += 1
        return counts

    def words_at(self, level: int) -> list[str]:
        level = _clamp(level)
        return [w for w, p in self._data.items() if _clamp(p.familiarity) == level]


def _clamp(level: int) -> int:
    return max(int(Familiarity.UNFAMILIAR), min(int(Familiarity.MASTERED), int(level)))
