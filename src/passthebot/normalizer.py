from __future__ import annotations

import re
from dataclasses import dataclass

from passthebot.graph import SkillEntry
from passthebot.validate_graph import normalize_string


@dataclass
class ExtractedKeyword:
    id: str
    category: str
    matched_text: str
    confidence: float


def extract_discrete_keywords(text: str, entries: list[SkillEntry]) -> list[ExtractedKeyword]:
    """Scan text for any known alias of any discrete-category entry.

    Matching is on normalized substrings (see normalize_string): case-insensitive,
    punctuation/whitespace-collapsed. Each skill id is reported at most once, even
    if multiple of its aliases (or the same alias multiple times) appear in the text.
    """
    normalized_text = normalize_string(text)
    found: dict[str, ExtractedKeyword] = {}
    for entry in entries:
        if entry.id in found:
            continue
        for alias in entry.aliases:
            needle = normalize_string(alias)
            if needle and re.search(
                rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", normalized_text
            ):
                found[entry.id] = ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=alias, confidence=1.0
                )
                break
    return list(found.values())


def extract_soft_skills(
    text: str, entries: list[SkillEntry], embedder
) -> list[ExtractedKeyword]:
    """Match soft_skills entries by embedding similarity against anchor_phrases.
    An entry is included if the best-matching anchor phrase clears its own
    embedding_threshold.
    """
    found: list[ExtractedKeyword] = []
    for entry in entries:
        if not entry.anchor_phrases:
            continue
        phrase, score = embedder.best_match(text, entry.anchor_phrases)
        if score >= (entry.embedding_threshold if entry.embedding_threshold is not None else 0.45):
            found.append(
                ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=phrase, confidence=score
                )
            )
    return found
