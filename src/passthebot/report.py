from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from passthebot.matcher import MatchResult


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


def build_report(
    results: list[MatchResult],
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
    }
