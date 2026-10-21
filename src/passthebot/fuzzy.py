"""Fuzzy string similarity helper for near-miss alias matching (not yet wired into extraction)."""

from __future__ import annotations

from rapidfuzz import fuzz
from rapidfuzz.distance import Levenshtein

# A typo changes one or two letters ("dockr", "Pyhton"). Long German
# compounds with a shared ending ("Finanzbuchhaltung" vs "Lohnbuchhaltung")
# clear the ratio threshold while differing in many letters.
MAX_TYPO_EDITS = 2


def fuzzy_best_match(
    term: str, candidates: list[str], threshold: float = 0.75
) -> tuple[str, float] | None:
    """Return the best-matching candidate string and its similarity (0..1) if it
    clears `threshold` and is at most MAX_TYPO_EDITS edits away, else None.
    Uses rapidfuzz's normalized Levenshtein ratio.
    """
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in candidates:
        if Levenshtein.distance(term.lower(), candidate.lower()) > MAX_TYPO_EDITS:
            continue
        score = fuzz.ratio(term.lower(), candidate.lower()) / 100.0
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_candidate is not None and best_score >= threshold:
        return best_candidate, best_score
    return None
