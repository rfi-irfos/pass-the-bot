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


def test_run_pipeline_auto_detects_required_ids_when_omitted():
    """When required_ids is omitted, the posting's own required/optional
    signal phrases decide it, per passthebot.requirement.detect_required_ids."""
    report = run_pipeline(
        "Python is required for this role. Docker experience is nice to have.",
        "Experienced Python developer, no Docker experience.",
        data_dir=DATA_DIR,
        repo_root=REPO_ROOT,
    )
    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["python"]["required"] is True
    assert by_id["docker"]["required"] is False


def test_run_pipeline_produces_near_miss_for_typo_in_resume():
    """A misspelled skill in the resume should surface as NEAR_MISS, not a
    silent MISSING, now that enrich_near_misses is wired in."""
    report = run_pipeline(
        "Docker is required for this role.",
        "Comfortable with dockr and other containerization tools.",
        {"docker"},
        DATA_DIR,
        REPO_ROOT,
    )
    docker_result = next(r for r in report["results"] if r["id"] == "docker")
    assert docker_result["status"] == "NEAR_MISS"
    assert docker_result["found_text"] == "dockr"


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


def test_run_pipeline_includes_metrics_with_all_sections_detected():
    resume_text = (
        "Contact\n"
        "jane@example.com\n"
        "\n"
        "Experience\n"
        "Five years of experience as a backend developer at a large company "
        "focused on Python and databases and cloud infrastructure and team leadership.\n"
        "\n"
        "Education\n"
        "Bachelor of Science in Computer Science from State University completed "
        "with honors and a focus on software engineering practices.\n"
        "\n"
        "Skills\n"
        "Python, Docker, Kubernetes, AWS, PostgreSQL"
    )
    report = run_pipeline(
        "Requires Python and Docker.", resume_text, {"python", "docker"}, DATA_DIR, REPO_ROOT
    )
    section_ids = {s["id"] for s in report["metrics"]["sections"]}
    assert section_ids == {"contact", "experience", "education", "skills"}
    assert all(s["found"] for s in report["metrics"]["sections"])
    assert report["metrics"]["readability"]["score"] is not None
    assert set(report["metrics"]["radar"].keys()) == {
        "required_skills_pct",
        "soft_skills_pct",
        "wording_accuracy_pct",
        "readability_pct",
        "section_completeness_pct",
    }


def test_run_pipeline_matches_open_requirements_outside_curated_catalog():
    """A posting requirement with no curated catalog entry (e.g. a skilled-
    trades skill) should still surface as a result via the open-vocabulary
    layer, not silently vanish."""
    posting = (
        "We need a skilled tradesperson.\n"
        "\n"
        "Requirements\n"
        "- Welding experience\n"
        "- Electrical wiring knowledge\n"
    )
    resume = "Five years of experience welding steel frames in an industrial workshop."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)
    open_results = {r["id"]: r for r in report["results"] if r["origin"] == "open"}
    assert set(open_results) == {"Welding experience", "Electrical wiring knowledge"}
    assert open_results["Welding experience"]["status"] in ("MATCH", "NEAR_MISS")


def test_run_pipeline_reports_open_requirement_as_missing_when_resume_is_unrelated():
    posting = "Requirements\n- Welding experience\n"
    resume = "Certified public accountant with ten years in corporate tax preparation."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)
    welding = next(r for r in report["results"] if r["id"] == "Welding experience")
    assert welding["status"] == "MISSING"


def test_run_pipeline_open_requirement_already_curated_is_not_duplicated():
    posting = "Requirements\n- Python\n- SQL\n"
    resume = "Experienced Python developer."
    report = run_pipeline(posting, resume, {"python"}, DATA_DIR, REPO_ROOT)
    python_results = [r for r in report["results"] if r["id"].lower() == "python"]
    assert len(python_results) == 1
    assert python_results[0]["origin"] == "curated"


def test_run_pipeline_open_phrase_matching_curated_soft_skill_anchor_is_not_duplicated():
    """A posting can mention a soft skill both in prose (triggering the
    curated soft_skills embedding match, whose matched_text is the
    catalog's own anchor phrasing) and again as an open-vocabulary-style
    bullet under a Requirements heading with slightly different wording.
    The literal claimed_spans whole-word check alone won't catch the
    inflected bullet phrasing, so this must be deduped by the new
    embedding-similarity check against the claimed entry's own
    anchor_phrases (Fix 4) -- otherwise the same concept surfaces twice,
    once under each layer."""
    posting = (
        "Wir arbeiten gerne im Team und schaetzen teamorientiert arbeiten sehr.\n"
        "\n"
        "Requirements\n"
        "- Teamorientiertes Arbeiten\n"
    )
    resume = "Ich arbeite gerne im Team und bin teamorientiert."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)

    open_duplicate = [r for r in report["results"] if r["id"] == "Teamorientiertes Arbeiten"]
    assert open_duplicate == []

    curated_teamwork = [r for r in report["results"] if r["id"] == "teamwork"]
    assert len(curated_teamwork) == 1
    assert curated_teamwork[0]["origin"] == "curated"


def test_run_pipeline_open_missing_requirement_counts_toward_required_coverage():
    """A posting requirement the curated catalog doesn't recognize at all
    (e.g. a skilled-trades posting) must count toward required_total, and
    when unmatched, must pull coverage_pct below 100 -- otherwise a
    posting like this silently reports 100% required-skill coverage on a
    0/0 basis, hiding exactly the blind spot open-vocabulary matching
    exists to fix."""
    posting = "Requirements\n- Welding experience\n"
    resume = "Certified public accountant with ten years in corporate tax preparation."
    report = run_pipeline(posting, resume, data_dir=DATA_DIR, repo_root=REPO_ROOT)
    welding = next(r for r in report["results"] if r["id"] == "Welding experience")
    assert welding["required"] is True
    assert welding["status"] == "MISSING"
    assert report["score"]["required_total"] >= 1
    assert report["score"]["coverage_pct"] < 100
