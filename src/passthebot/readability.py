"""Readability metric for resume text, per the honest-dashboard design spec.

Uses the Automated Readability Index (ARI), a real, named formula that
needs no syllable-counting step, so it works the same way for German and
English text without a per-language heuristic:

    ARI = 4.71 * (characters / words) + 0.5 * (words / sentences) - 21.43

ARI produces a US school grade-level number. For display, that grade
level is linearly rescaled to a 0-100 "readability score" (grade 0 -> 100,
grade 20 -> 0, clamped): score = clamp(100 - grade_level * 5, 0, 100).
This is a display rescale of a real formula, not an invented multi-factor
score.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from passthebot.normalizer import split_sentences

MIN_WORDS_FOR_SCORE = 5
MIN_SENTENCES_FOR_SCORE = 2

_NON_WORD_CHARS = re.compile(r"[^\w]", re.UNICODE)


@dataclass
class ReadabilityResult:
    score: float | None
    grade_level: float | None
    avg_words_per_sentence: float
    avg_word_length_chars: float


def _word_length(word: str) -> int:
    """Character length of a word with surrounding punctuation stripped,
    so a trailing comma or period doesn't inflate the average word length."""
    return len(_NON_WORD_CHARS.sub("", word))


def compute_readability(text: str) -> ReadabilityResult:
    sentences = split_sentences(text)
    words = text.split()
    word_count = len(words)
    sentence_count = len(sentences)

    avg_words_per_sentence = round(word_count / sentence_count, 1) if sentence_count else 0.0
    char_count = sum(_word_length(w) for w in words)
    avg_word_length_chars = round(char_count / word_count, 1) if word_count else 0.0

    if word_count < MIN_WORDS_FOR_SCORE or sentence_count < MIN_SENTENCES_FOR_SCORE:
        return ReadabilityResult(
            score=None,
            grade_level=None,
            avg_words_per_sentence=avg_words_per_sentence,
            avg_word_length_chars=avg_word_length_chars,
        )

    grade_level = 4.71 * avg_word_length_chars + 0.5 * avg_words_per_sentence - 21.43
    score = max(0.0, min(100.0, 100 - grade_level * 5))

    return ReadabilityResult(
        score=round(score, 1),
        grade_level=round(grade_level, 1),
        avg_words_per_sentence=avg_words_per_sentence,
        avg_word_length_chars=avg_word_length_chars,
    )
