"""Shared reading-analysis logic used by both the CLI scripts and the web server.

Builds a per-word index for a piece of text (translation, phonetic, difficulty,
frequency and the learner's current familiarity), and renders an interactive
HTML body where every word is clickable.
"""

from __future__ import annotations

import html
from dataclasses import dataclass

from .models import GRADED_LEVEL_LABELS, Familiarity, WordEntry
from .progress import ProgressStore
from .textscan import LemmaResolver, iter_word_spans, lookup_ecdict, tokenize

# Familiarity colours, matching the flashcard UI.
FAM_COLOR = {1: "#ef4444", 2: "#f59e0b", 3: "#eab308", 4: "#84cc16", 5: "#22c55e"}
UNKNOWN_COLOR = "#a855f7"  # word outside the graded vocabulary


def clean(text: str) -> str:
    """Normalise ECDICT translation whitespace (drop stray carriage returns)."""

    return text.replace("\\r", "").replace("\r", "").replace("\\n", "\n").strip()


@dataclass(slots=True)
class WordInfo:
    headword: str
    phonetic: str
    translation: str
    difficulty: str | None
    coca: int | None
    familiarity: int
    in_vocab: bool
    # True when the word lives in a pool outside the 5-level process (ignored
    # or already mastered): it is shown but never highlighted, and is skipped
    # by the glossary.
    excluded: bool = False

    def color(self) -> str:
        if not self.in_vocab:
            return UNKNOWN_COLOR
        return FAM_COLOR.get(self.familiarity, FAM_COLOR[1])

    def difficulty_label(self) -> str:
        if self.difficulty:
            return GRADED_LEVEL_LABELS.get(self.difficulty, self.difficulty)
        return "生词 New" if not self.in_vocab else "—"

    def to_dict(self) -> dict:
        return {
            "headword": self.headword,
            "phonetic": self.phonetic,
            "translation": self.translation,
            "difficulty": self.difficulty,
            "difficulty_label": self.difficulty_label(),
            "coca": self.coca,
            "familiarity": self.familiarity,
            "familiarity_label": Familiarity(self.familiarity).label,
            "in_vocab": self.in_vocab,
        }


def build_index(
    text: str,
    dataset: dict[str, WordEntry],
    resolver: LemmaResolver,
    store: ProgressStore,
    include_unknown: bool = True,
) -> dict[str, WordInfo]:
    """Return ``token -> WordInfo`` for every distinct word in ``text``.

    Inflected tokens resolve to their graded head word; words outside the graded
    vocabulary are looked up in the full ECDICT (single streaming pass).
    """

    index: dict[str, WordInfo] = {}
    unknown: set[str] = set()
    tokens = list(dict.fromkeys(tokenize(text)))

    for token in tokens:
        if not token:
            continue
        base = resolver.resolve(token)
        if base is not None:
            entry = dataset[base]
            index[token] = WordInfo(
                headword=entry.word,
                phonetic=entry.phonetic,
                translation=clean(entry.translation),
                difficulty=entry.difficulty,
                coca=entry.coca,
                familiarity=int(store.familiarity(base)),
                in_vocab=True,
            )
        elif include_unknown:
            unknown.add(token)

    if include_unknown and unknown:
        for token, data in lookup_ecdict(unknown).items():
            translation = clean(data.get("translation", ""))
            if not translation:
                continue
            index[token] = WordInfo(
                headword=token,
                phonetic=data.get("phonetic", ""),
                translation=translation,
                difficulty=None,
                coca=None,
                familiarity=int(store.familiarity(token)),
                in_vocab=False,
            )

    # ECDICT lookup order is independent of the source text, so restore the
    # order in which each distinct token first appeared before returning.
    return {token: index[token] for token in tokens if token in index}


def render_reading_body(
    text: str,
    index: dict[str, WordInfo],
    max_familiarity: int,
    min_familiarity: int = 1,
) -> str:
    """Render ``text`` as HTML: every known word is a clickable ``<span>``.

    Words whose familiarity falls within the inclusive
    ``[min_familiarity, max_familiarity]`` range are visually highlighted; all
    known words carry the data attributes needed for the tap-to-translate panel
    and the click-to-reduce-familiarity action.
    """

    pieces: list[str] = []
    pos = 0
    for start, end, word in iter_word_spans(text):
        pieces.append(html.escape(text[pos:start]))
        raw = text[start:end]
        info = index.get(word)
        if info is not None:
            highlight = (not info.excluded) and (
                min_familiarity <= info.familiarity <= max_familiarity
            )
            style = f"background:{info.color()}" if highlight else ""
            tip = info.translation.split("\n")[0]
            pieces.append(
                f'<span class="w{" hl" if highlight else ""}" '
                f'data-hw="{html.escape(info.headword)}" '
                f'data-tr="{html.escape(info.translation)}" '
                f'data-ph="{html.escape(info.phonetic)}" '
                f'data-fam="{info.familiarity}" '
                f'data-vocab="{1 if info.in_vocab else 0}" '
                f'data-excluded="{1 if info.excluded else 0}" '
                f'style="{style}" title="{html.escape(tip)}">'
                f"{html.escape(raw)}</span>"
            )
        else:
            pieces.append(html.escape(raw))
        pos = end
    pieces.append(html.escape(text[pos:]))
    return "".join(pieces)


def glossary_entries(
    index: dict[str, WordInfo],
    max_familiarity: int | None = None,
    *,
    sort_by_frequency: bool = True,
) -> list[WordInfo]:
    """Return de-duplicated word infos sorted by frequency.

    If ``max_familiarity`` is given, only words at or below that familiarity are
    returned (i.e. the ones still worth studying).
    """

    unique: dict[str, WordInfo] = {}
    for info in index.values():
        if info.excluded:
            continue
        if max_familiarity is not None and info.familiarity > max_familiarity:
            continue
        unique.setdefault(info.headword.lower(), info)

    entries = list(unique.values())
    if not sort_by_frequency:
        return entries
    return sorted(
        entries,
        key=lambda i: (i.coca if i.coca is not None else 10**9, i.headword.lower()),
    )
