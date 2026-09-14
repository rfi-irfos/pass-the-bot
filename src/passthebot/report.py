from __future__ import annotations

import subprocess
from dataclasses import asdict
from pathlib import Path

from passthebot.matcher import MatchResult


def get_graph_version(repo_root: Path) -> str:
    """Return the current HEAD commit hash of repo_root, or 'unknown' if
    repo_root is not inside a git repository (e.g. a fresh checkout without
    history, or a non-git deployment)."""
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
    results: list[MatchResult], graph_version: str, engine_version: str = "0.1.0"
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
        "results": [asdict(r) for r in results],
        "score": {
            "required_matched": required_matched,
            "required_total": required_total,
            "coverage_pct": coverage_pct,
        },
    }
