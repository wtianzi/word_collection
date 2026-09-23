import unittest
from vocab.morphemes import MorphemeDictionary

class MorphemeDictionaryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.dictionary = MorphemeDictionary()
    def test_has_all_three_kinds(self):
        counts=self.dictionary.counts(); self.assertGreater(counts["prefix"],20); self.assertGreater(counts["root"],20); self.assertGreater(counts["suffix"],15)
    def test_searches_forms_without_dashes(self): self.assertTrue(any(x["form"]=="-ion" for x in self.dictionary.search("tion")))
    def test_searches_meanings_and_examples(self):
        self.assertTrue(any(x["form"]=="bio" for x in self.dictionary.search("生命"))); self.assertTrue(any(x["form"]=="port" for x in self.dictionary.search("portable")))
    def test_filters_kind(self):
        matches=self.dictionary.search("","suffix"); self.assertTrue(matches); self.assertTrue(all(x["kind"]=="suffix" for x in matches))

    def test_explains_curated_word_with_multiple_parts(self):
        result = self.dictionary.explain("transport")
        self.assertEqual({part["form"] for part in result["parts"]}, {"trans-", "port"})
        self.assertIn("运输", result["note"])

    def test_explains_productive_prefix_only_with_known_base(self):
        result = self.dictionary.explain("unfair", {"fair", "unfair"})
        self.assertEqual(result["parts"][0]["form"], "un-")
        self.assertEqual(result["note"], "词干：fair")

    def test_does_not_guess_from_letters_alone(self):
        self.assertEqual(self.dictionary.explain("qwerty", {"qwerty"})["parts"], [])

    def test_supplementary_dictionary_covers_unlisted_words(self):
        result = self.dictionary.explain("astronomy")
        self.assertEqual(result["language"], "en")
        self.assertTrue(any("star" in part["meaning"] for part in result["parts"]))
        self.assertGreater(len(self.dictionary.supplementary_index), 10000)

if __name__ == "__main__": unittest.main()
