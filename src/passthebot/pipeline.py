from __future__ import annotations

from pathlib import Path

from passthebot.embeddings import Embedder
from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.matcher import enrich_near_misses, match
from passthebot.normalizer import extract_discrete_keywords, extract_soft_skills
from passthebot.report import build_report, get_graph_version
from passthebot.requirement import detect_required_ids
from passthebot.validate_graph import validate_graph


class PipelineInputError(Exception):
    """Raised when posting_text or resume_text is empty/unparseable, per spec
    section 7: never silently return a zero-signal report for bad input."""


def run_pipeline(
    posting_text: str,
    resume_text: str,
    required_ids: set[str] | None = None,
    data_dir: Path | None = None,
    repo_root: Path | None = None,
    embedder: Embedder | None = None,
) -> dict:
    """The single entry point downstream products (candidate checker, KMU
    agent) call. Loads the graph, validates it, extracts keywords from both
    texts, matches them, and returns the versioned JSON-shaped report dict.

    data_dir defaults to the skill YAML files bundled inside the installed
    package. repo_root defaults to this repo's root (three levels up from
    this file); if that's not inside a git repo (e.g. a real pip-installed
    deployment with no .git anywhere), get_graph_version already falls back
    to "unknown".

    required_ids defaults to None, in which case which posting-side skills
    count as "required" is auto-detected from the posting text itself (see
    passthebot.requirement.detect_required_ids) instead of the caller having
    to name skill ids manually. Pass an explicit set to override detection.
    """
    if not posting_text.strip():
        raise PipelineInputError("posting_text is empty or whitespace-only")
    if not resume_text.strip():
        raise PipelineInputError("resume_text is empty or whitespace-only")

    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR
    if repo_root is None:
        repo_root = Path(__file__).resolve().parents[2]

    entries = active_entries(load_skill_graph(data_dir))
    validate_graph(entries)
    embedder = embedder or Embedder()

    posting_kw = extract_discrete_keywords(posting_text, entries) + extract_soft_skills(
        posting_text, entries, embedder
    )
    resume_kw = extract_discrete_keywords(resume_text, entries) + extract_soft_skills(
        resume_text, entries, embedder
    )

    if required_ids is None:
        required_ids = detect_required_ids(posting_text, posting_kw)

    results = match(posting_kw, resume_kw, required_ids)
    results = enrich_near_misses(results, resume_text, entries)
    return build_report(
        results,
        graph_version=get_graph_version(repo_root),
        model_version=getattr(embedder, "model_name", "unknown"),
    )
