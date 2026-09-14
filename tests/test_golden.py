from pathlib import Path

from passthebot.graph import DEFAULT_DATA_DIR
from passthebot.pipeline import run_pipeline

REPO_ROOT = Path(__file__).parent.parent
DATA_DIR = DEFAULT_DATA_DIR
GOLDEN_DIR = Path(__file__).parent / "golden"


def test_golden_posting_1_resume_1():
    posting_text = (GOLDEN_DIR / "posting_1.txt").read_text()
    resume_text = (GOLDEN_DIR / "resume_1.txt").read_text()
    required_ids = {"python", "docker"}  # matches "Required:" line in posting_1.txt

    report = run_pipeline(posting_text, resume_text, required_ids, DATA_DIR, REPO_ROOT)

    by_id = {r["id"]: r for r in report["results"]}
    assert by_id["python"]["status"] == "MATCH"
    assert by_id["docker"]["status"] == "MATCH"
    assert by_id["react"]["status"] == "MISSING"
    assert by_id["teamwork"]["status"] == "MATCH"

    assert report["score"]["required_total"] == 2
    assert report["score"]["required_matched"] == 2
    assert report["score"]["coverage_pct"] == 100.0
