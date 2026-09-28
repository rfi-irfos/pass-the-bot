from pathlib import Path

from passthebot.matcher import MatchResult
from passthebot.report import build_report, get_graph_version

RESULTS = [
    MatchResult(id="python", category="languages", status="MATCH", required=True),
    MatchResult(id="docker", category="tools", status="MISSING", required=True),
    MatchResult(
        id="kubernetes", category="tools", status="NEAR_MISS", required=False,
        found_text="k8s", suggested_alias="Kubernetes", confidence=0.8,
    ),
]

RESUME_TEXT = (
    "Experience\n"
    "Five years of experience as a backend developer at a large company "
    "focused on Python and databases and cloud infrastructure and team leadership.\n"
    "\n"
    "Skills\n"
    "Python, Docker, Kubernetes"
)


def test_build_report_shape():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["engine_version"] == "0.1.0"
    assert report["graph_version"] == "abc123"
    assert report["model_version"] == "unknown"
    assert len(report["results"]) == 3


def test_build_report_includes_provided_model_version():
    report = build_report(
        RESULTS, RESUME_TEXT, graph_version="abc123", model_version="all-MiniLM-L6-v2"
    )
    assert report["model_version"] == "all-MiniLM-L6-v2"


def test_build_report_score_counts_only_required():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 1
    assert report["score"]["coverage_pct"] == 50.0


def test_build_report_includes_metrics_match_breakdown():
    results_with_soft_skill = RESULTS + [
        MatchResult(id="teamwork", category="soft_skills", status="MATCH", required=False),
    ]
    report = build_report(results_with_soft_skill, RESUME_TEXT, graph_version="abc123")
    breakdown = report["metrics"]["match_breakdown"]
    assert breakdown == {
        "exact_matched": 1,
        "exact_total": 3,
        "semantic_matched": 1,
        "semantic_total": 1,
    }


def test_build_report_includes_metrics_sections_and_readability():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    metrics = report["metrics"]
    section_ids = {s["id"] for s in metrics["sections"]}
    assert section_ids == {"contact", "experience", "education", "skills"}
    experience = next(s for s in metrics["sections"] if s["id"] == "experience")
    assert experience["found"] is True
    assert metrics["readability"]["score"] is not None


def test_build_report_radar_has_five_axes():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    radar = report["metrics"]["radar"]
    assert set(radar.keys()) == {
        "required_skills_pct",
        "soft_skills_pct",
        "wording_accuracy_pct",
        "readability_pct",
        "section_completeness_pct",
    }
    assert radar["required_skills_pct"] == 50.0


def test_build_report_radar_defaults_soft_skills_to_100_when_none_present():
    report = build_report(RESULTS, RESUME_TEXT, graph_version="abc123")
    assert report["metrics"]["radar"]["soft_skills_pct"] == 100.0


def test_build_report_handles_empty_results_without_crashing():
    report = build_report([], RESUME_TEXT, graph_version="abc123")
    assert report["metrics"]["radar"]["wording_accuracy_pct"] == 100.0
    assert report["score"]["coverage_pct"] == 100.0


def test_get_graph_version_returns_a_git_hash_in_a_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    expected_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    version = get_graph_version(tmp_path)
    assert len(version) == 40
    assert version == expected_hash


def test_get_graph_version_returns_unknown_outside_git_repo(tmp_path):
    version = get_graph_version(tmp_path)
    assert version == "unknown"


def test_build_report_open_origin_results_count_as_semantic_not_exact():
    results_with_open = RESULTS + [
        MatchResult(
            id="Welding experience", category="open_requirements", status="MATCH",
            required=False, origin="open",
        ),
    ]
    report = build_report(results_with_open, RESUME_TEXT, graph_version="abc123")
    breakdown = report["metrics"]["match_breakdown"]
    assert breakdown["exact_total"] == 3
    assert breakdown["semantic_total"] == 1
    assert breakdown["semantic_matched"] == 1
