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

    Span-claiming semantics: overlapping aliases from different entries
    resolve to the longest match. If a shorter entry's alias falls fully
    inside a span already claimed by a longer, different entry's alias, the
    shorter entry is NOT also extracted for that occurrence (e.g. once a
    "React Native" entry exists alongside a "react" entry, the text "React
    Native experience" extracts only react_native, not react, for that
    occurrence). This is an intentional design choice, not a bug: a single
    mention is not double-counted as both the specific and the more general
    skill it happens to contain as a substring.
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
        for m in re.finditer(
            rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", normalized_text
        ):
            start, end = m.start(), m.end()
            if any(claimed[start:end]):
                continue
            for i in range(start, end):
                claimed[i] = True
            if entry.id not in found:
                found[entry.id] = ExtractedKeyword(
                    id=entry.id, category=entry.category, matched_text=alias, confidence=1.0
                )
    return list(found.values())


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on . ! ? boundaries and newlines, dropping
    empty fragments.

    A simple regex split is sufficient for V1 - no NLP library needed. Embedding
    the whole document as one vector dilutes short soft-skill mentions buried in
    a multi-sentence posting/resume, so callers should score sentence-by-sentence
    instead of scoring the whole text at once. Splitting also on newlines is
    required because real job postings are commonly formatted as bullet lists
    with no terminal punctuation per line (e.g. "- Python\\n- Teamfaehigkeit"),
    which would otherwise collapse into one large fragment and reintroduce the
    same dilution problem.
    """
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
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
        threshold = entry.embedding_threshold if entry.embedding_threshold is not None else 0.48
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
