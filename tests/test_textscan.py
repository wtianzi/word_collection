"""Regression tests for reading-material tokenization."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from vocab.models import WordEntry
from vocab.textscan import (
    SUPPORTED_SUFFIXES,
    LemmaResolver,
    extract_text,
    iter_word_spans,
    tokenize,
)
from vocab.reading import paginate_text


class TokenizeTests(unittest.TestCase):
    def test_common_subtitle_formats_are_read_as_plain_text(self) -> None:
        subtitle_suffixes = {".srt", ".vtt", ".ass", ".ssa", ".sub", ".sbv", ".lrc", ".smi", ".ttml", ".dfxp"}
        self.assertTrue(subtitle_suffixes <= SUPPORTED_SUFFIXES)
        with TemporaryDirectory() as root:
            path = Path(root) / "sample.srt"
            content = "1\n00:00:01,000 --> 00:00:03,000\nHello world!\n"
            path.write_text(content, encoding="utf-8")
            self.assertEqual(extract_text(path), content)

    def test_reading_pages_preserve_all_text_and_prefer_newlines(self) -> None:
        text = "a" * 110 + "\n" + "b" * 79
        pages = paginate_text(text, page_size=100)

        self.assertEqual("".join(pages), text)
        self.assertEqual(len(pages), 2)
        self.assertTrue(pages[0].endswith("\n"))

    def test_reading_pages_follow_chapter_boundaries(self) -> None:
        text = (
            "Book title\n\nChapter 1: Start\n" + "a" * 150 + "\n"
            "Chapter 2: Next\n" + "b" * 150
        )
        pages = paginate_text(text, page_size=100)

        self.assertEqual(len(pages), 2)
        self.assertEqual("".join(pages), text)
        self.assertTrue(pages[0].startswith("Book title\n\nChapter 1: Start"))
        self.assertTrue(pages[1].startswith("Chapter 2: Next"))

    def test_chinese_chapter_headings_are_page_boundaries(self) -> None:
        text = "序言\n第一章 开始\n内容\n第二回 后续\n内容"

        self.assertEqual(
            paginate_text(text),
            ["序言\n第一章 开始\n内容\n", "第二回 后续\n内容"],
        )

    def test_hyphenated_compounds_are_separate_words(self) -> None:
        text = "self-aware state-of-the-art self aware"

        self.assertEqual(
            tokenize(text),
            ["self", "aware", "state", "of", "the", "art", "self", "aware"],
        )

    def test_internal_apostrophes_remain_part_of_words(self) -> None:
        self.assertEqual(tokenize("don't teachers'"), ["don't", "teachers"])

    def test_word_spans_leave_hyphens_between_words(self) -> None:
        text = "alpha-beta"
        spans = list(iter_word_spans(text))

        self.assertEqual(spans, [(0, 5, "alpha"), (6, 10, "beta")])
        self.assertEqual([text[start:end] for start, end, _ in spans], ["alpha", "beta"])


class LemmaResolverTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dataset = {
            "run": WordEntry(
                word="run",
                exchange={"p": "ran", "d": "run", "i": "running", "3": "runs"},
            ),
            # These forms deliberately also exist as headwords.  They must not
            # become separate learning records when ECDICT names a base word.
            "running": WordEntry(word="running", exchange={"0": "run", "1": "i"}),
            "see": WordEntry(word="see", exchange={"p": "saw", "d": "seen"}),
            "saw": WordEntry(word="saw", exchange={"0": "see", "1": "p"}),
            "study": WordEntry(word="study"),
            "studying": WordEntry(word="studying", exchange={"0": "studied"}),
            "studied": WordEntry(word="studied", exchange={"0": "study"}),
            "numb": WordEntry(word="numb", coca=9000, exchange={"r": "number"}),
            "number": WordEntry(
                word="number", coca=200, exchange={"0": "numb", "1": "r"}
            ),
        }
        self.resolver = LemmaResolver(self.dataset)

    def test_all_common_verb_forms_share_the_headword(self) -> None:
        self.assertEqual(self.resolver.resolve("run"), "run")
        self.assertEqual(self.resolver.resolve("runs"), "run")
        self.assertEqual(self.resolver.resolve("ran"), "run")
        self.assertEqual(self.resolver.resolve("running"), "run")

    def test_explicit_lemma_wins_over_an_exact_headword(self) -> None:
        self.assertEqual(self.resolver.resolve("saw"), "see")

    def test_regular_fallback_still_handles_missing_exchange_data(self) -> None:
        self.assertEqual(self.resolver.resolve("studies"), "study")

    def test_chained_dictionary_lemmas_reach_a_stable_base(self) -> None:
        self.assertEqual(self.resolver.resolve("studying"), "study")

    def test_common_independent_word_is_not_changed_to_a_rare_lemma(self) -> None:
        self.assertEqual(self.resolver.resolve("number"), "number")


if __name__ == "__main__":
    unittest.main()
