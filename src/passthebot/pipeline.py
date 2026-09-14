from __future__ import annotations

from pathlib import Path

from passthebot.embeddings import Embedder
from passthebot.graph import active_entries, load_skill_graph
from passthebot.matcher import match
from passthebot.normalizer import extract_discrete_keywords, extract_soft_skills
from passthebot.report import build_report, get_graph_version
from passthebot.validate_graph import validate_graph


class PipelineInputError(Exception):
    """Raised when posting_text or resume_text is empty/unparseable, per spec
    section 7: never silently return a zero-signal report for bad input."""


def run_pipeline(
    posting_text: str,
    resume_text: str,
    required_ids: set[str],
    data_dir: Path,
    repo_root: Path,
    embedder: Embedder | None = None,
) -> dict:
    """The single entry point downstream products (candidate checker, KMU
    agent) call. Loads the graph, validates it, extracts keywords from both
    texts, matches them, and returns the versioned JSON-shaped report dict.
    """
    if not posting_text.strip():
        raise PipelineInputError("posting_text is empty or whitespace-only")
    if not resume_text.strip():
        raise PipelineInputError("resume_text is empty or whitespace-only")

    entries = active_entries(load_skill_graph(data_dir))
    validate_graph(entries)
    embedder = embedder or Embedder()

    posting_kw = extract_discrete_keywords(posting_text, entries) + extract_soft_skills(
        posting_text, entries, embedder
    )
    resume_kw = extract_discrete_keywords(resume_text, entries) + extract_soft_skills(
        resume_text, entries, embedder
    )

    results = match(posting_kw, resume_kw, required_ids)
    return build_report(results, graph_version=get_graph_version(repo_root))
