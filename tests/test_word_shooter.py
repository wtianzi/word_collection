import random
import unittest

from vocab.word_shooter import WordShooterSession, mastery_response


class WordShooterSessionTests(unittest.TestCase):
    def test_correct_and_wrong_answers_update_stats(self):
        session = WordShooterSession(["peculiar", "gaze"], seed=1)
        session.record("peculiar", False)
        self.assertEqual(session.stats["peculiar"].wrong_count, 1)
        session.record("peculiar", True)
        self.assertEqual(session.stats["peculiar"].correct_count, 1)

    def test_missed_word_has_higher_repetition_priority(self):
        session = WordShooterSession(["peculiar", "gaze", "reluctant"], seed=1)
        session.record("peculiar", False)
        session.record("gaze", True)
        self.assertEqual(session.next_word(list(session.stats), "reluctant"), "peculiar")

    def test_choices_contain_correct_answer_exactly_once(self):
        choices = WordShooterSession.choices("gaze", ["gaze", "gaze", "peculiar", "reluctant"], 3, random.Random(2))
        self.assertEqual(choices.count("gaze"), 1)
        self.assertEqual(len(choices), 3)

    def test_session_completes_after_repeated_correct_recall(self):
        session = WordShooterSession(["a", "b"])
        for word in ("a", "b", "a", "b"):
            session.record(word, True)
        self.assertTrue(session.complete())

    def test_mastery_mapping_is_conservative(self):
        self.assertIsNone(mastery_response(0, 0))
        self.assertEqual(mastery_response(2, 1), "hard")
        self.assertEqual(mastery_response(2, 0), "good")


if __name__ == "__main__":
    unittest.main()
