"""Compares posting keywords against resume keywords by canonical id and scores coverage."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from passthebot.fuzzy import fuzzy_best_match
from passthebot.graph import DISCRETE_CATEGORIES, SkillEntry
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

    This function only ever produces MATCH/MISSING. NEAR_MISS is applied
    afterward as a separate enrichment pass by `enrich_near_misses` below,
    keeping this function's canonical-id comparison pure and deterministic.
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


def enrich_near_misses(
    results: list[MatchResult],
    resume_text: str,
    entries: list[SkillEntry],
    threshold: float = 0.75,
) -> list[MatchResult]:
    """Upgrade MISSING results to NEAR_MISS when a fuzzy-string hit against
    that same skill's own aliases is found in the raw resume text.

    This is a separate pass from `match()`, deliberately: it never compares
    one id against a different id's aliases, it only asks "does something
    close to *this exact skill's own* known aliases appear in the resume,
    even though no exact alias matched during extraction?" Only discrete
    categories are considered; soft_skills are already matched via embedding
    similarity during extraction, so a second, string-based fuzzy pass over
    them would be redundant and could produce a misleading suggested_alias
    for a category with no fixed alias strings.

    Known V1 limitation: tokens are single words (regex below), so a
    multi-word alias typo (e.g. "React Natvie" for "React Native") is not
    caught, only single-token typos (e.g. "dockr" -> "Docker"). Threshold
    reuses fuzzy_best_match's own default (0.75), not yet validated against
    real postings/resumes.
    """
    entries_by_id = {e.id: e for e in entries}
    tokens = re.findall(r"[A-Za-zÀ-ÿ0-9][A-Za-zÀ-ÿ0-9+.#-]*", resume_text)

    enriched: list[MatchResult] = []
    for result in results:
        entry = entries_by_id.get(result.id)
        if (
            result.status != "MISSING"
            or entry is None
            or entry.category not in DISCRETE_CATEGORIES
            or not entry.aliases
        ):
            enriched.append(result)
            continue

        best_token: str | None = None
        best_alias: str | None = None
        best_score = 0.0
        for token in tokens:
            hit = fuzzy_best_match(token, entry.aliases, threshold=threshold)
            if hit is not None and hit[1] > best_score:
                best_alias, best_score = hit
                best_token = token

        if best_token is not None:
            enriched.append(
                replace(
                    result,
                    status="NEAR_MISS",
                    found_text=best_token,
                    suggested_alias=best_alias,
                    confidence=best_score,
                )
            )
        else:
            enriched.append(result)
    return enriched
