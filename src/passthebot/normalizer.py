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

    Uses longest-alias-first matching with span-claiming: normalization turns
    punctuation like "." into a space (e.g. "Node.js" -> "node js"), which means
    a short alias belonging to a *different* entry (e.g. "js" for javascript) can
    accidentally match as a standalone token inside a longer alias's normalized
    text ("node js"). To avoid this, all (alias, entry) pairs are tried longest-
    normalized-alias-first, and once a span of the normalized text is claimed by
    a match, no shorter alias is allowed to match inside that span. This is the
    same failure class as the Java/JavaScript regression case (design spec
    section 8), just reached via punctuation normalization instead of a raw
    substring collision.
    """
    normalized_text = normalize_string(text)
    claimed = [False] * len(normalized_text)

    pairs: list[tuple[str, str, SkillEntry]] = []
    for entry in entries:
        for alias in entry.aliases:
            needle = normalize_string(alias)
            if needle:
                pairs.append((needle, alias, entry))
    pairs.sort(key=lambda p: len(p[0]), reverse=True)

    found: dict[str, ExtractedKeyword] = {}
    for needle, alias, entry in pairs:
        if entry.id in found:
            continue
        for m in re.finditer(
            rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", normalized_text
        ):
            start, end = m.start(), m.end()
            if any(claimed[start:end]):
                continue
            for i in range(start, end):
                claimed[i] = True
            found[entry.id] = ExtractedKeyword(
                id=entry.id, category=entry.category, matched_text=alias, confidence=1.0
            )
            break
    return list(found.values())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries, dropping empty fragments.

    A simple regex split is sufficient for V1 - no NLP library needed. Embedding
    the whole document as one vector dilutes short soft-skill mentions buried in
    a multi-sentence posting/resume, so callers should score sentence-by-sentence
    instead of scoring the whole text at once.
    """
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences if s.strip()]


def extract_soft_skills(
    text: str, entries: list[SkillEntry], embedder
) -> list[ExtractedKeyword]:
    """Match soft_skills entries by embedding similarity against anchor_phrases.

    The input text is split into sentences and each sentence is scored
    independently against an entry's anchor_phrases; the highest-scoring
    (phrase, score) pair across all sentences is used. Scoring the whole
    document as a single embedding dilutes short soft-skill mentions buried
    in longer multi-sentence text, so per-sentence scoring is required to
    detect them reliably.

    An entry is included if the best-matching anchor phrase (across all
    sentences) clears its own embedding_threshold.
    """
    sentences = _split_sentences(text)
    if not sentences:
        sentences = [text]

    found: list[ExtractedKeyword] = []
    for entry in entries:
        if not entry.anchor_phrases:
            continue
        best_phrase: str | None = None
        best_score = float("-inf")
        for sentence in sentences:
            phrase, score = embedder.best_match(sentence, entry.anchor_phrases)
            if score > best_score:
                best_phrase, best_score = phrase, score
        threshold = entry.embedding_threshold if entry.embedding_threshold is not None else 0.45
        if best_score >= threshold:
            found.append(
                ExtractedKeyword(
                    id=entry.id,
                    category=entry.category,
                    matched_text=best_phrase,
                    confidence=best_score,
                )
            )
    return found
