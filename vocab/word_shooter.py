"""Learning-session logic for the Word Shooter game.

The browser owns animation and presentation; this module owns the deterministic
rules that are useful to validate independently of the UI.
"""

from __future__ import annotations

import random
from dataclasses import dataclass


@dataclass
class ShooterStat:
    word: str
    times_shown: int = 0
    correct_count: int = 0
    wrong_count: int = 0
    consecutive_correct: int = 0
    last_seen: int = -99
    introduced: bool = False


class WordShooterSession:
    """Small adaptive scheduler shared by tests and documented for the client."""

    def __init__(self, words: list[str], seed: int | None = None) -> None:
        if not words:
            raise ValueError("a session needs at least one word")
        self.stats = {word: ShooterStat(word) for word in dict.fromkeys(words)}
        self.question_index = 0
        self.random = random.Random(seed)

    def record(self, word: str, correct: bool) -> None:
        stat = self.stats[word]
        stat.times_shown += 1
        stat.last_seen = self.question_index
        if correct:
            stat.correct_count += 1
            stat.consecutive_correct += 1
        else:
            stat.wrong_count += 1
            stat.consecutive_correct = 0
        self.question_index += 1

    def next_word(self, available: list[str], previous: str | None = None) -> str:
        candidates = [w for w in available if w != previous] or list(available)
        # Mistakes dominate, unseen words follow, then stale/least-mastered words.
        def priority(word: str) -> float:
            s = self.stats[word]
            age = self.question_index - s.last_seen
            return s.wrong_count * 8 + (4 if not s.times_shown else 0) + age * .3 - s.consecutive_correct * 2 + self.random.random()

        return max(candidates, key=priority)

    @staticmethod
    def choices(correct: str, available: list[str], count: int, rng: random.Random) -> list[str]:
        distractors = list(dict.fromkeys(w for w in available if w != correct))
        rng.shuffle(distractors)
        result = distractors[: max(0, count - 1)] + [correct]
        rng.shuffle(result)
        return result

    def complete(self, required_correct: int = 2) -> bool:
        return all(s.correct_count >= required_correct for s in self.stats.values())


def mastery_response(correct_count: int, wrong_count: int) -> str | None:
    """Map a meaningful game result onto the application's review vocabulary."""

    if correct_count <= 0:
        return None
    if wrong_count:
        return "hard"
    return "good" if correct_count >= 2 else "hard"
