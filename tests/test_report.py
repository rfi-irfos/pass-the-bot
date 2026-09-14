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


def test_build_report_shape():
    report = build_report(RESULTS, graph_version="abc123")
    assert report["engine_version"] == "0.1.0"
    assert report["graph_version"] == "abc123"
    assert len(report["results"]) == 3


def test_build_report_score_counts_only_required():
    report = build_report(RESULTS, graph_version="abc123")
    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 1
    assert report["score"]["coverage_pct"] == 50.0


def test_get_graph_version_returns_a_git_hash_in_a_repo(tmp_path):
    import subprocess

    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    (tmp_path / "file.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-m", "x"],
        cwd=tmp_path, check=True, capture_output=True,
    )
    # Get the expected hash via git rev-parse HEAD
    expected_hash = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    version = get_graph_version(tmp_path)
    assert len(version) == 40  # full git SHA
    assert version == expected_hash  # verify it matches the actual HEAD commit


def test_get_graph_version_returns_unknown_outside_git_repo(tmp_path):
    version = get_graph_version(tmp_path)
    assert version == "unknown"
