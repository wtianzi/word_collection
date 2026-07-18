"""Load and normalize the raw resources into a single in-memory dataset.

The dictionary data (``resources/dict/ecdict.csv``) is the source of truth for
meanings, phonetics and frequency ranks.  The graded word lists in
``resources/wordlists/`` are used to tag each word with the syllabus levels it
belongs to (primary school ... GRE).

The combined vocabulary is the *union* of every graded list, which keeps the
dataset compact (tens of thousands of relevant words) instead of the full
~770k ECDICT rows.
"""

from __future__ import annotations

import csv
import pickle
import re
import sys
from pathlib import Path

from .models import WordEntry

# Allow arbitrarily large dictionary fields (some ECDICT rows are big).
csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESOURCES = PROJECT_ROOT / "resources"
ECDICT_CSV = RESOURCES / "dict" / "ecdict.csv"
WORDLISTS_DIR = RESOURCES / "wordlists"
CACHE_FILE = PROJECT_ROOT / "data" / "dataset_cache.pkl"

# Word-list file -> level id.  ``coca20000`` is not a graded syllabus level but
# is kept as membership + used as a frequency fallback.
WORDLIST_FILES: dict[str, str] = {
    "primary_school.txt": "primary",
    "middle_school_zhongkao.txt": "zhongkao",
    "high_school_gaokao.txt": "gaokao",
    "CET4.txt": "cet4",
    "CET6.txt": "cet6",
    "TOEFL.txt": "toefl",
    "GRE_8000.txt": "gre",
    "COCA_20000.txt": "coca20000",
}

# A head word: an ASCII letter followed by letters / apostrophes / hyphens.
_HEADWORD_RE = re.compile(r"^([A-Za-z][A-Za-z'\-]*)")


def _extract_headword(line: str) -> str | None:
    """Pull the English head word from the start of a word-list line.

    Handles plain lists (``abandon``), annotated lists
    (``abandon [ə'bændən] v. 放弃``) and skips section headers / titles /
    Chinese lines.
    """

    line = line.strip()
    if not line:
        return None
    match = _HEADWORD_RE.match(line)
    if not match:
        return None
    word = match.group(1).lower().strip("-'")
    if not word:
        return None
    return word


def load_wordlists() -> tuple[dict[str, set[str]], dict[str, int]]:
    """Return ``(word -> set(levels), word -> coca_rank)``."""

    levels: dict[str, set[str]] = {}
    coca_rank: dict[str, int] = {}

    for filename, level in WORDLIST_FILES.items():
        path = WORDLISTS_DIR / filename
        if not path.exists():
            continue
        rank = 0
        with path.open(encoding="utf-8", errors="ignore") as fp:
            for line in fp:
                word = _extract_headword(line)
                if not word:
                    continue
                levels.setdefault(word, set()).add(level)
                if level == "coca20000":
                    rank += 1
                    # keep the first (most frequent) occurrence
                    coca_rank.setdefault(word, rank)

    return levels, coca_rank


def _parse_exchange(raw: str) -> dict[str, str]:
    """Parse ECDICT ``exchange`` field (``p:did/d:done/s:plural``)."""

    result: dict[str, str] = {}
    if not raw:
        return result
    for part in raw.split("/"):
        if ":" in part:
            key, _, value = part.partition(":")
            if value:
                result[key] = value
    return result


def _to_int(value: str) -> int | None:
    value = (value or "").strip()
    if not value or value == "0":
        return None
    try:
        return int(value)
    except ValueError:
        return None


def build_dataset() -> dict[str, WordEntry]:
    """Build the normalized ``word -> WordEntry`` dataset."""

    levels, coca_rank = load_wordlists()
    vocabulary = set(levels)

    entries: dict[str, WordEntry] = {}

    if ECDICT_CSV.exists():
        with ECDICT_CSV.open(encoding="utf-8", errors="ignore", newline="") as fp:
            reader = csv.DictReader(fp)
            for row in reader:
                word = (row.get("word") or "").strip()
                key = word.lower()
                if key not in vocabulary:
                    continue
                if key in entries:
                    continue
                tag = (row.get("tag") or "").strip()
                entries[key] = WordEntry(
                    word=word,
                    phonetic=(row.get("phonetic") or "").strip(),
                    definition=(row.get("definition") or "").replace("\\n", "\n").strip(),
                    translation=(row.get("translation") or "").replace("\\n", "\n").strip(),
                    pos=(row.get("pos") or "").strip(),
                    collins=_to_int(row.get("collins", "")),
                    oxford=(row.get("oxford") or "").strip() == "1",
                    exam_tags=tag.split() if tag else [],
                    bnc=_to_int(row.get("bnc", "")),
                    coca=_to_int(row.get("frq", "")),
                    exchange=_parse_exchange((row.get("exchange") or "").strip()),
                    levels=sorted(levels.get(key, set())),
                )

    # Include list words missing from ECDICT so the vocabulary stays complete.
    for key in vocabulary:
        if key not in entries:
            entries[key] = WordEntry(word=key, levels=sorted(levels[key]))

    # Fallback COCA rank from the COCA_20000 ordering where ECDICT lacks it.
    for key, entry in entries.items():
        if entry.coca is None and key in coca_rank:
            entry.coca = coca_rank[key]

    return entries


def _resources_mtime() -> float:
    paths = [ECDICT_CSV, *(WORDLISTS_DIR / f for f in WORDLIST_FILES)]
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def load_dataset(use_cache: bool = True) -> dict[str, WordEntry]:
    """Load the dataset, using a pickle cache when the resources are unchanged."""

    if use_cache and CACHE_FILE.exists():
        try:
            if CACHE_FILE.stat().st_mtime >= _resources_mtime():
                with CACHE_FILE.open("rb") as fp:
                    return pickle.load(fp)
        except (OSError, pickle.PickleError):
            pass

    dataset = build_dataset()

    if use_cache:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with CACHE_FILE.open("wb") as fp:
                pickle.dump(dataset, fp)
        except OSError:
            pass

    return dataset


if __name__ == "__main__":
    data = load_dataset(use_cache=False)
    print(f"Loaded {len(data):,} words")
    for sample in ("hello", "abandon", "ubiquitous", "the"):
        entry = data.get(sample)
        if entry:
            print(
                f"  {entry.word:<14} coca={entry.coca} "
                f"difficulty={entry.difficulty} levels={entry.levels}"
            )
            print(f"    {entry.translation.splitlines()[0] if entry.translation else '(no translation)'}")
