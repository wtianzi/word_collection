"""Data models for the vocabulary trainer.

Two distinct level concepts are used in this project:

* ``difficulty`` – an *objective* grading of a word coming from published
  syllabus word lists (primary school -> ... -> GRE).  It never changes.
* ``Familiarity`` – a *subjective* 5-level scale describing how well the
  current learner knows a word.  It changes as the learner studies.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum


# Objective difficulty, ordered from easiest to hardest.  The identifiers match
# the membership tags produced by :mod:`vocab.loader`.
GRADED_LEVELS: tuple[str, ...] = (
    "primary",  # 小学
    "zhongkao",  # 中考 (middle school)
    "gaokao",  # 高考 (high school)
    "cet4",  # 大学英语四级
    "cet6",  # 大学英语六级
    "toefl",  # TOEFL
    "gre",  # GRE
)

GRADED_LEVEL_LABELS: dict[str, str] = {
    "primary": "小学 Primary",
    "zhongkao": "中考 Middle",
    "gaokao": "高考 High",
    "cet4": "四级 CET-4",
    "cet6": "六级 CET-6",
    "toefl": "TOEFL",
    "gre": "GRE",
}


class Familiarity(IntEnum):
    """How well the learner knows a word, on a 5-point scale."""

    UNFAMILIAR = 1  # 陌生 – never learned / did not recognise
    LEARNING = 2  # 学习中 – currently learning, still shaky
    FAMILIAR = 3  # 熟悉 – recognised with some effort
    PROFICIENT = 4  # 熟练 – recalled quickly and confidently
    MASTERED = 5  # 掌握 – fully mastered

    @property
    def label(self) -> str:
        return FAMILIARITY_LABELS[self]


FAMILIARITY_LABELS: dict[Familiarity, str] = {
    Familiarity.UNFAMILIAR: "陌生 Unfamiliar",
    Familiarity.LEARNING: "学习中 Learning",
    Familiarity.FAMILIAR: "熟悉 Familiar",
    Familiarity.PROFICIENT: "熟练 Proficient",
    Familiarity.MASTERED: "掌握 Mastered",
}


@dataclass(slots=True)
class WordEntry:
    """A single normalized vocabulary entry.

    Combines the ECDICT dictionary data with membership in the graded word
    lists.  The per-learner familiarity is stored separately (see
    :mod:`vocab.progress`) so that the dictionary dataset stays immutable and
    shareable.
    """

    word: str
    phonetic: str = ""
    definition: str = ""  # English definition(s)
    translation: str = ""  # Chinese translation(s)
    pos: str = ""  # part-of-speech ratios, e.g. "n:46/v:54"
    collins: int | None = None  # Collins star rating 1-5
    oxford: bool = False  # in the Oxford 3000 core list
    exam_tags: list[str] = field(default_factory=list)  # ecdict tags: zk/gk/...
    bnc: int | None = None  # BNC frequency rank
    coca: int | None = None  # COCA frequency rank (ecdict "frq")
    exchange: dict[str, str] = field(default_factory=dict)  # inflected forms
    levels: list[str] = field(default_factory=list)  # graded list membership

    @property
    def difficulty(self) -> str | None:
        """Easiest graded level the word appears in, or ``None`` if unknown."""

        for level in GRADED_LEVELS:
            if level in self.levels:
                return level
        return None

    @property
    def frequency_rank(self) -> int | None:
        """Best available frequency rank (prefer COCA, fall back to BNC)."""

        if self.coca:
            return self.coca
        return self.bnc

    def to_dict(self) -> dict:
        return {
            "word": self.word,
            "phonetic": self.phonetic,
            "definition": self.definition,
            "translation": self.translation,
            "pos": self.pos,
            "collins": self.collins,
            "oxford": self.oxford,
            "exam_tags": self.exam_tags,
            "bnc": self.bnc,
            "coca": self.coca,
            "exchange": self.exchange,
            "levels": self.levels,
            "difficulty": self.difficulty,
            "frequency_rank": self.frequency_rank,
        }
