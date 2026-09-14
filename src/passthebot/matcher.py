from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from passthebot.normalizer import ExtractedKeyword

Status = Literal["MATCH", "NEAR_MISS", "MISSING"]


@dataclass
class MatchResult:
    id: str
    category: str
    status: Status
    required: bool
    found_text: str | None = None
    suggested_alias: str | None = None
    confidence: float | None = None


def match(
    posting_keywords: list[ExtractedKeyword],
    resume_keywords: list[ExtractedKeyword],
    required_ids: set[str],
) -> list[MatchResult]:
    """For every keyword found in the posting, decide whether the resume
    satisfies it by canonical id (never by raw text). No fuzzy fallback across
    different ids happens here (fuzzy matching is used inside extraction for a
    single skill's own aliases, Task 4, not to conflate two different ids).
    """
    resume_ids = {k.id for k in resume_keywords}
    results: list[MatchResult] = []
    for posting_kw in posting_keywords:
        if posting_kw.id in resume_ids:
            results.append(
                MatchResult(
                    id=posting_kw.id,
                    category=posting_kw.category,
                    status="MATCH",
                    required=posting_kw.id in required_ids,
                )
            )
        else:
            results.append(
                MatchResult(
                    id=posting_kw.id,
                    category=posting_kw.category,
                    status="MISSING",
                    required=posting_kw.id in required_ids,
                )
            )
    return results
