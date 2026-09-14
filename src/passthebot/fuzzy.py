"""Fuzzy string similarity helper for near-miss alias matching (not yet wired into extraction)."""

from __future__ import annotations

from rapidfuzz import fuzz


def fuzzy_best_match(
    term: str, candidates: list[str], threshold: float = 0.75
) -> tuple[str, float] | None:
    """Return the best-matching candidate string and its similarity (0..1) if it
    clears `threshold`, else None. Uses rapidfuzz's normalized Levenshtein ratio.
    """
    best_candidate: str | None = None
    best_score = 0.0
    for candidate in candidates:
        score = fuzz.ratio(term.lower(), candidate.lower()) / 100.0
        if score > best_score:
            best_score = score
            best_candidate = candidate
    if best_candidate is not None and best_score >= threshold:
        return best_candidate, best_score
    return None
