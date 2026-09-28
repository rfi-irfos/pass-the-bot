"""Compares posting keywords against resume keywords by canonical id and scores coverage."""

from __future__ import annotations

import re
from dataclasses import dataclass, replace
from typing import Literal

from passthebot.fuzzy import fuzzy_best_match
from passthebot.graph import DISCRETE_CATEGORIES, SkillEntry
from passthebot.normalizer import ExtractedKeyword, OpenRequirement, split_sentences
from passthebot.validate_graph import normalize_string

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
    origin: Literal["curated", "open"] = "curated"


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


def _phrase_already_claimed(key: str, claimed_spans: set[str]) -> bool:
    """True if a normalized open-requirement phrase (`key`) contains any
    already-claimed curated span as a whole word.

    Reuses the same word-boundary containment check used elsewhere in this
    codebase for the identical class of problem (see
    normalizer.extract_discrete_keywords's "Java/JavaScript regression
    case" docstring and sections.py's _heading_matches), so that a bare
    claimed span like "python" is recognized inside a full bullet phrase
    like "erfahrung mit python", while a span like "java" does not
    falsely match inside "javascript".
    """
    return any(
        span and re.search(rf"(?<![a-z0-9]){re.escape(span)}(?![a-z0-9])", key)
        for span in claimed_spans
    )


def match_open_requirements(
    open_requirements: list[OpenRequirement],
    resume_text: str,
    embedder,
    claimed_spans: set[str],
    match_threshold: float = 0.48,
    near_miss_threshold: float = 0.35,
) -> list[MatchResult]:
    """Classify each open-vocabulary requirement phrase (from
    normalizer.extract_open_requirements, independent of any curated
    skill catalog) against the resume text by embedding similarity,
    using the same Embedder.best_match mechanism as
    normalizer.extract_soft_skills -- here with the roles reversed: the
    open requirement phrase plays the role of the "text being scored"
    and the resume's own sentences play the role of the candidate
    phrases it's compared against, so the returned best match is the
    single resume sentence closest to this requirement.

    claimed_spans holds the normalized (via validate_graph.normalize_string)
    matched_text of every curated posting-side match already found for
    this posting; an open phrase whose normalized text is already in
    claimed_spans is skipped entirely, so a skill covered by both the
    curated catalog and an open requirements bullet in the same posting
    is reported exactly once (the curated match wins). Duplicate open
    phrases within the same posting collapse to a single result the
    same way.

    Returned MatchResult.id is the requirement phrase's own literal text
    (there is no canonical id for an open phrase); origin is "open" so
    callers (report.py, the frontend) can distinguish these from
    curated, exact-alias matches without re-deriving it from confidence
    or category.

    Every returned result has required=True: an open-vocabulary phrase is
    definitionally extracted from a requirements-style heading
    (normalizer.extract_open_requirements only looks under
    REQUIREMENT_HEADING_KEYWORDS), so it represents an actual stated
    requirement, not an optional extra -- unlike curated matches, there is
    no separate signal-phrase pass (passthebot.requirement) distinguishing
    required vs. nice-to-have for open phrases, so all of them count
    toward required coverage.

    MISSING results carry confidence=None, not the raw sub-threshold
    score, matching the convention used elsewhere in this module (match()
    and enrich_near_misses) that confidence is only populated when
    something was actually found.
    """
    sentences = split_sentences(resume_text)
    if not sentences:
        sentences = [resume_text]

    results: list[MatchResult] = []
    seen: set[str] = set()
    for req in open_requirements:
        key = normalize_string(req.phrase)
        if not key or key in seen or _phrase_already_claimed(key, claimed_spans):
            continue
        seen.add(key)

        best_sentence, score = embedder.best_match(
            req.phrase, sentences, cache_phrases=False
        )
        if score >= match_threshold:
            status: Status = "MATCH"
        elif score >= near_miss_threshold:
            status = "NEAR_MISS"
        else:
            status = "MISSING"

        results.append(
            MatchResult(
                id=req.phrase,
                category="open_requirements",
                status=status,
                required=True,
                found_text=best_sentence if status != "MISSING" else None,
                confidence=score if status != "MISSING" else None,
                origin="open",
            )
        )
    return results
