"""Non-tech job postings (finance, office, care, sales, marketing, trades).

The postings in tests/data/postings/ are synthetic, modelled on real
DACH and English listings. Each has a hand-written gold file; see
scripts/measure_postings.py for the format and a recall report.
"""

from pathlib import Path

import pytest
import yaml

from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.normalizer import extract_discrete_keywords, extract_open_requirements

POSTINGS_DIR = Path(__file__).parent / "data" / "postings"
POSTINGS = sorted(POSTINGS_DIR.glob("*.txt"))
ENTRIES = active_entries(load_skill_graph(DEFAULT_DATA_DIR))


def _load(posting: Path) -> tuple[str, dict]:
    gold = yaml.safe_load(posting.with_suffix(".expected.yaml").read_text())
    return posting.read_text(), gold


@pytest.mark.parametrize("posting", POSTINGS, ids=lambda p: p.stem)
def test_expected_skills_are_found(posting):
    text, gold = _load(posting)
    found = {k.id for k in extract_discrete_keywords(text, ENTRIES)}
    assert set(gold["expected"]) - found == set()


@pytest.mark.parametrize("posting", POSTINGS, ids=lambda p: p.stem)
def test_no_false_tech_skills(posting):
    text, gold = _load(posting)
    found = {k.id for k in extract_discrete_keywords(text, ENTRIES)}
    assert set(gold["forbidden"]) & found == set()


@pytest.mark.parametrize("posting", POSTINGS, ids=lambda p: p.stem)
def test_open_requirements_keep_requirements_and_drop_benefits(posting):
    text, gold = _load(posting)
    phrases = [r.phrase.lower() for r in extract_open_requirements(text)]
    for wanted in gold["open_expected"]:
        assert any(wanted in p for p in phrases), wanted
    for benefit in gold["open_forbidden"]:
        assert not any(benefit in p for p in phrases), benefit


def test_every_posting_has_a_gold_file():
    assert len(POSTINGS) == 12
    for posting in POSTINGS:
        assert posting.with_suffix(".expected.yaml").exists()


@pytest.mark.parametrize(
    "text, wrong_id",
    [
        ("Excellent writing skills", "excel"),
        ("Standort Deutschland, Kunden in Germany", "german"),
        ("Experience with Kubernetes scheduling", "scheduling"),
        ("Work with our Customer Success Managers (CSM)", "scrum_master"),
        ("Datenpflege im ERP-System", "basic_care"),
        ("Subscribe to our newsletter", "email_marketing"),
        ("Staplerführerschein von Vorteil", "drivers_license"),
        ("Elektromeister gesucht", "electrician"),
    ],
)
def test_catalog_does_not_confuse_similar_words(text, wrong_id):
    found = {k.id for k in extract_discrete_keywords(text, ENTRIES)}
    assert wrong_id not in found
