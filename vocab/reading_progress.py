"""Per-book reading progress, persisted to a JSON file.

Remembers how far the learner has read in each uploaded book so the reading
position survives tab switches, reloads and moving between devices.  Progress is
keyed by the upload file name and stores both a scroll offset (to jump back to
the exact spot) and a 0-100 percentage (shown on the library page).

Stored as ``data/reading_progress.json`` so it lives on the server rather than
in a single browser's ``localStorage``.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_READING_PROGRESS_FILE = PROJECT_ROOT / "data" / "reading_progress.json"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class BookProgress:
    percent: int = 0  # 0-100, how far through the book
    scroll: int = 0  # pixel offset to restore the exact reading position
    updated: str = ""

    def to_dict(self) -> dict:
        return {"percent": self.percent, "scroll": self.scroll, "updated": self.updated}

    @classmethod
    def from_dict(cls, data: dict) -> "BookProgress":
        return cls(
            percent=_clamp_percent(data.get("percent", 0)),
            scroll=max(0, _as_int(data.get("scroll", 0))),
            updated=str(data.get("updated", "")),
        )


def _as_int(value: object) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _clamp_percent(value: object) -> int:
    return max(0, min(100, _as_int(value)))


class ReadingProgressStore:
    """Thread-safe JSON-backed store of per-book reading progress."""

    def __init__(self, path: Path | str = DEFAULT_READING_PROGRESS_FILE) -> None:
        self._path = Path(path)
        self._lock = threading.Lock()
        self._data: dict[str, BookProgress] = {}
        self._load()

    # ------------------------------------------------------------------ io
    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        books = raw.get("books", raw) if isinstance(raw, dict) else {}
        if isinstance(books, dict):
            self._data = {
                str(name): BookProgress.from_dict(info)
                for name, info in books.items()
                if isinstance(info, dict)
            }

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"books": {name: bp.to_dict() for name, bp in self._data.items()}}
        tmp = self._path.with_suffix(self._path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        tmp.replace(self._path)

    # --------------------------------------------------------------- access
    def get(self, name: str) -> BookProgress | None:
        return self._data.get(name)

    def all(self) -> dict[str, BookProgress]:
        return dict(self._data)

    def set(self, name: str, percent: int, scroll: int) -> BookProgress:
        """Store the reading position for ``name`` and persist it."""

        key = (name or "").strip()
        if not key:
            raise ValueError("book name is required")
        bp = BookProgress(
            percent=_clamp_percent(percent),
            scroll=max(0, _as_int(scroll)),
            updated=_now(),
        )
        with self._lock:
            self._data[key] = bp
            self._save()
        return bp

    def remove(self, name: str) -> bool:
        key = (name or "").strip()
        with self._lock:
            if key not in self._data:
                return False
            del self._data[key]
            self._save()
        return True
