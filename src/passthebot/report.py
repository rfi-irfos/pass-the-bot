from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from passthebot.matcher import MatchResult
from passthebot.readability import compute_readability
from passthebot.sections import SectionResult, detect_sections


def get_graph_version(repo_root: Path) -> str:
    """Return the current HEAD commit hash of the entire repository.

    This returns the repository-wide HEAD commit, not a hash scoped to any
    specific subdirectory (e.g. data/skills/). This is intentional: it captures
    both the skill data AND the matching-code version together for full
    reproducibility and auditability. Two reports with identical skill data but
    different matcher-code logic will have different graph_version values,
    preserving audit trail integrity.

    Returns 'unknown' if repo_root is not inside a git repository (e.g. a fresh
    checkout without history, or a non-git deployment) or if the git binary is
    not available."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _match_breakdown(results: list[MatchResult]) -> dict:
    """Split matched results into exact (discrete alias match) vs semantic
    (soft_skills embedding match). MatchResult.category already carries this
    distinction; this is pure aggregation, no new computation."""
    exact = [r for r in results if r.category != "soft_skills"]
    semantic = [r for r in results if r.category == "soft_skills"]
    return {
        "exact_matched": sum(1 for r in exact if r.status == "MATCH"),
        "exact_total": len(exact),
        "semantic_matched": sum(1 for r in semantic if r.status == "MATCH"),
        "semantic_total": len(semantic),
    }


def _build_radar(
    results: list[MatchResult],
    required_matched: int,
    required_total: int,
    readability_score: float | None,
    sections: list[SectionResult],
) -> dict:
    """Assemble the 5-axis radar from values already computed elsewhere.
    Every axis is a plain percentage a user could recompute by hand."""
    required_skills_pct = (
        round(100.0 * required_matched / required_total, 1) if required_total else 100.0
    )

    soft_skill_results = [r for r in results if r.category == "soft_skills"]
    soft_skills_pct = (
        round(100.0 * sum(1 for r in soft_skill_results if r.status == "MATCH") / len(soft_skill_results), 1)
        if soft_skill_results
        else 100.0
    )

    near_miss_count = sum(1 for r in results if r.status == "NEAR_MISS")
    wording_accuracy_pct = (
        round(100.0 - 100.0 * near_miss_count / len(results), 1) if results else 100.0
    )

    filled_sections = sum(1 for s in sections if s.filled)
    section_completeness_pct = (
        round(100.0 * filled_sections / len(sections), 1) if sections else 100.0
    )

    return {
        "required_skills_pct": required_skills_pct,
        "soft_skills_pct": soft_skills_pct,
        "wording_accuracy_pct": wording_accuracy_pct,
        "readability_pct": readability_score,
        "section_completeness_pct": section_completeness_pct,
    }


def build_report(
    results: list[MatchResult],
    resume_text: str,
    graph_version: str,
    engine_version: str = "0.1.0",
    model_version: str = "unknown",
) -> dict:
    required_results = [r for r in results if r.required]
    required_total = len(required_results)
    required_matched = sum(1 for r in required_results if r.status == "MATCH")
    coverage_pct = (
        round(100.0 * required_matched / required_total, 1) if required_total else 100.0
    )

    readability = compute_readability(resume_text)
    sections = detect_sections(resume_text)

    return {
        "engine_version": engine_version,
        "graph_version": graph_version,
        "model_version": model_version,
        "results": [asdict(r) for r in results],
        "score": {
            "required_matched": required_matched,
            "required_total": required_total,
            "coverage_pct": coverage_pct,
        },
        "metrics": {
            "readability": asdict(readability),
            "sections": [asdict(s) for s in sections],
            "match_breakdown": _match_breakdown(results),
            "radar": _build_radar(
                results, required_matched, required_total, readability.score, sections
            ),
        },
    }
