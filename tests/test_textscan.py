"""Regression tests for reading-material tokenization."""

import unittest

from vocab.textscan import iter_word_spans, tokenize


class TokenizeTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
