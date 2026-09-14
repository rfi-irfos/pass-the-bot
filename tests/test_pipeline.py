from pathlib import Path

import pytest

from passthebot.graph import DEFAULT_DATA_DIR
from passthebot.pipeline import PipelineInputError, run_pipeline

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = DEFAULT_DATA_DIR


def test_run_pipeline_rejects_empty_posting_text():
    with pytest.raises(PipelineInputError, match="posting_text"):
        run_pipeline("", "Some resume text.", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_rejects_empty_resume_text():
    with pytest.raises(PipelineInputError, match="resume_text"):
        run_pipeline("Some posting text.", "", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_rejects_whitespace_only_text():
    with pytest.raises(PipelineInputError):
        run_pipeline("   \n  ", "Some resume text.", {"python"}, DATA_DIR, REPO_ROOT)


def test_run_pipeline_returns_valid_report_shape():
    report = run_pipeline(
        "Requires Python.", "Experienced Python developer.", {"python"}, DATA_DIR, REPO_ROOT
    )
    assert "engine_version" in report
    assert "graph_version" in report
    assert "model_version" in report
    assert "results" in report
    assert "score" in report


def test_run_pipeline_uses_default_data_dir_and_repo_root_when_omitted():
    """data_dir and repo_root are optional; omitting them should use the
    package's bundled data and the real repo root, and still produce a
    valid report."""
    report = run_pipeline("Requires Python.", "Experienced Python developer.", {"python"})
    assert "engine_version" in report
    assert "model_version" in report
    assert report["graph_version"] != "unknown"


class _StubEmbedderWithoutModelName:
    """Duck-typed embedder stub deliberately without a model_name attribute,
    mirroring what a caller's test double might pass in."""

    def best_match(self, sentence: str, phrases: list[str]):
        return phrases[0], 0.0


def test_run_pipeline_tolerates_embedder_without_model_name_attribute():
    """extract_soft_skills only requires a best_match method on embedder (it's
    duck-typed), but the pipeline used to read embedder.model_name directly,
    which would AttributeError on a minimal stub. It must fall back to a
    placeholder instead of crashing."""
    report = run_pipeline(
        "Requires Python.",
        "Experienced Python developer.",
        {"python"},
        DATA_DIR,
        REPO_ROOT,
        embedder=_StubEmbedderWithoutModelName(),
    )
    assert report["model_version"] == "unknown"
