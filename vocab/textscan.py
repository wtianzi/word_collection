"""Shared helpers for scanning reading material (papers / books).

Supports plain text, Markdown, HTML, PDF and EPUB.  Provides tokenisation and a
lemmatiser built from the ECDICT inflection data so that words such as
``running`` / ``studies`` / ``abandoned`` are mapped back to the base word that
appears in our vocabulary.
"""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path
from typing import Iterable, Iterator

from .loader import ECDICT_CSV
from .models import WordEntry

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

TEXT_SUFFIXES = {".txt", ".text", ".md", ".markdown"}
HTML_SUFFIXES = {".html", ".htm", ".xhtml"}
SUPPORTED_SUFFIXES = TEXT_SUFFIXES | HTML_SUFFIXES | {".pdf", ".epub"}

# A word token: ASCII letters with optional internal apostrophes. Hyphens are
# deliberately separators so compounds such as ``state-of-the-art`` share the
# same entries as their individual words instead of creating duplicate terms.
WORD_RE = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)*")

# ECDICT exchange keys that hold an inflected form of the head word.
_INFLECTION_KEYS = ("p", "d", "i", "3", "r", "t", "s")


# --------------------------------------------------------------------------- io
def extract_text(path: Path) -> str:
    """Extract plain text from a supported file, best effort."""

    suffix = path.suffix.lower()
    if suffix in TEXT_SUFFIXES:
        return path.read_text(encoding="utf-8", errors="ignore")
    if suffix in HTML_SUFFIXES:
        return _html_to_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        return _pdf_to_text(path)
    if suffix == ".epub":
        return _epub_to_text(path)
    # Unknown extension: try as UTF-8 text.
    return path.read_text(encoding="utf-8", errors="ignore")


def _html_to_text(html: str) -> str:
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style"]):
        tag.decompose()
    return soup.get_text(" ")


def _pdf_to_text(path: Path) -> str:
    from pypdf import PdfReader

    reader = PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception:  # noqa: BLE001 - skip unreadable pages
            continue
    return "\n".join(parts)


def _epub_to_text(path: Path) -> str:
    import ebooklib
    from bs4 import BeautifulSoup
    from ebooklib import epub

    book = epub.read_epub(str(path))
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        soup = BeautifulSoup(item.get_content(), "lxml")
        parts.append(soup.get_text(" "))
    return "\n".join(parts)


def iter_text_files(target: Path) -> Iterator[Path]:
    """Yield supported files under ``target`` (a file or directory)."""

    if target.is_file():
        yield target
        return
    for path in sorted(target.rglob("*")):
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES:
            yield path


# ------------------------------------------------------------------- tokenising
def tokenize(text: str) -> list[str]:
    """Return lower-cased word tokens from ``text``."""

    return [m.group(0).lower() for m in WORD_RE.finditer(text)]


def iter_word_spans(text: str) -> Iterator[tuple[int, int, str]]:
    """Yield ``(start, end, lowercased_word)`` for each word in ``text``."""

    for m in WORD_RE.finditer(text):
        yield m.start(), m.end(), m.group(0).lower()


# ------------------------------------------------------------------ lemmatising
class LemmaResolver:
    """Map an arbitrary token to a head word present in ``dataset``.

    Uses each entry's ECDICT ``exchange`` inflections (plurals, tenses, ...) to
    build a reverse ``inflection -> lemma`` index.
    """

    def __init__(self, dataset: dict[str, WordEntry]) -> None:
        self._dataset = dataset
        self._inflections: dict[str, str] = {}
        for key, entry in dataset.items():
            # "0" in exchange is this word's own lemma, if it is an inflection.
            lemma = entry.exchange.get("0")
            if lemma:
                self._inflections.setdefault(lemma.lower(), key)
            for infl_key in _INFLECTION_KEYS:
                form = entry.exchange.get(infl_key)
                if form:
                    self._inflections.setdefault(form.lower(), key)

    def resolve(self, token: str) -> str | None:
        """Return the vocabulary head word for ``token`` or ``None``."""

        token = token.lower()
        if token in self._dataset:
            return token
        if token in self._inflections:
            return self._inflections[token]
        # Simple morphological fall-backs for regular forms.
        for base in _naive_bases(token):
            if base in self._dataset:
                return base
        return None


def _naive_bases(token: str) -> Iterable[str]:
    """Cheap regular-inflection guesses, tried only as a last resort."""

    if token.endswith("ies") and len(token) > 4:
        yield token[:-3] + "y"
    if token.endswith("es") and len(token) > 3:
        yield token[:-2]
    if token.endswith("s") and len(token) > 2:
        yield token[:-1]
    if token.endswith("ed") and len(token) > 3:
        yield token[:-2]
        yield token[:-1]
        if len(token) > 4 and token[-3] == token[-4]:
            yield token[:-3]  # stopped -> stop
    if token.endswith("ing") and len(token) > 4:
        yield token[:-3]
        yield token[:-3] + "e"  # making -> make
        if len(token) > 5 and token[-4] == token[-5]:
            yield token[:-4]  # running -> run


# --------------------------------------------------------- full ECDICT look-ups
def lookup_ecdict(words: set[str]) -> dict[str, dict[str, str]]:
    """Fetch phonetic + translation for ``words`` from the full ECDICT.

    Streams the CSV once and returns ``{word: {"phonetic": .., "translation":
    ..}}`` for the words that were found.  Useful for words that appear in a
    paper but are outside the graded vocabulary.
    """

    wanted = {w.lower() for w in words}
    found: dict[str, dict[str, str]] = {}
    if not wanted or not ECDICT_CSV.exists():
        return found
    with ECDICT_CSV.open(encoding="utf-8", errors="ignore", newline="") as fp:
        reader = csv.DictReader(fp)
        for row in reader:
            key = (row.get("word") or "").strip().lower()
            if key in wanted and key not in found:
                found[key] = {
                    "phonetic": (row.get("phonetic") or "").strip(),
                    "translation": (row.get("translation") or "")
                    .replace("\\n", "\n")
                    .strip(),
                }
                if len(found) == len(wanted):
                    break
    return found
