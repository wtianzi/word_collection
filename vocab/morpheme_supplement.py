"""Exact word-to-morpheme index from Colin Goldberg's MIT-licensed dataset."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path


DATA_FILE = (
    Path(__file__).resolve().parent.parent
    / "resources" / "dict" / "morphemes_colingoldberg.json"
)
WORD_RE = re.compile(r"^[a-z]+$")
KINDS = {"prefix": "prefix", "embedded": "root", "suffix": "suffix"}


def load_index(path: Path = DATA_FILE) -> dict[str, list[dict]]:
    """Index source examples only when the marked morpheme fits the word."""

    source = json.loads(path.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = defaultdict(list)
    for item in source.values():
        meanings = [value.strip() for value in item.get("meaning", []) if isinstance(value, str) and value.strip()]
        if not meanings:
            continue
        meaning = "; ".join(meanings[:2])
        for example in item.get("examples", []):
            word = example.lower().strip()
            if not WORD_RE.fullmatch(word):
                continue
            matches = []
            for form in item.get("forms", []):
                location = form.get("loc")
                letters = str(form.get("form", "")).lower()
                if location not in KINDS or len(letters) < 3 or not WORD_RE.fullmatch(letters):
                    continue
                if location == "prefix" and word.startswith(letters):
                    start = 0
                elif location == "suffix" and word.endswith(letters):
                    start = len(word) - len(letters)
                elif location == "embedded" and letters in word:
                    start = word.index(letters)
                else:
                    continue
                matches.append({
                    "form": str(form.get("root") or letters),
                    "kind": KINDS[location],
                    "meaning": meaning,
                    "start": start,
                    "end": start + len(letters),
                })
            if matches:
                index[word].append(max(matches, key=lambda part: part["end"] - part["start"]))
    return dict(index)


def explain(index: dict[str, list[dict]], word: str) -> list[dict]:
    """Choose up to three non-overlapping forms, longest matches first."""

    candidates = sorted(
        index.get(word, []),
        key=lambda part: (part["start"] - part["end"], part["start"]),
    )
    selected = []
    for part in candidates:
        if any(part["start"] < other["end"] and other["start"] < part["end"] for other in selected):
            continue
        selected.append(part)
        if len(selected) == 3:
            break
    return [
        {key: part[key] for key in ("form", "kind", "meaning")}
        for part in sorted(selected, key=lambda part: part["start"])
    ]
