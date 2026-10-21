"""Posting and resume in different languages (German posting, English resume
and the other way round). Discrete skills meet across languages through their
DE/EN aliases; these tests guard that the right resume still scores high and
an unrelated one stays low."""

from pathlib import Path

import pytest

from passthebot.normalizer import _short_list_items
from passthebot.pipeline import run_pipeline

DATA = Path(__file__).parent / "data"

PAIRS = {
    "care_de_pflege": "care_en_nurse",
    "finance_de_buchhaltung": "finance_en_accountant",
    "office_de_assistenz": "office_en_office_manager",
    "marketing_en_content": "marketing_de_managerin",
}

RIGHT_MIN_PCT = 60
WRONG_MAX_PCT = 30


def _report(posting: str, resume: str, embedder) -> dict:
    return run_pipeline(
        (DATA / "postings" / f"{posting}.txt").read_text(encoding="utf-8"),
        (DATA / "resumes" / f"{resume}.txt").read_text(encoding="utf-8"),
        embedder=embedder,
    )


@pytest.fixture(scope="module")
def embedder():
    from passthebot.embeddings import Embedder

    return Embedder()


@pytest.mark.parametrize("posting", PAIRS)
def test_matching_resume_in_other_language_scores_high(posting, embedder):
    report = _report(posting, PAIRS[posting], embedder)
    assert report["score"]["coverage_pct"] >= RIGHT_MIN_PCT


@pytest.mark.parametrize(
    "posting,resume",
    [(p, r) for p in PAIRS for r in PAIRS.values() if PAIRS[p] != r],
)
def test_unrelated_resume_scores_low(posting, resume, embedder):
    report = _report(posting, resume, embedder)
    assert report["score"]["coverage_pct"] <= WRONG_MAX_PCT


def test_open_requirement_covered_by_skill_alias_is_not_reported(embedder):
    # "Buchhaltung" is an alias of bookkeeping, which the posting already
    # names as "Finanzbuchhaltung"; the bullet must not show up as an open
    # requirement the English resume ("Bookkeeping") seems to miss.
    report = _report("finance_de_buchhaltung", "finance_en_accountant", embedder)
    open_ids = [r["id"] for r in report["results"] if r.get("origin") == "open"]
    assert not any("Buchhaltung" in i for i in open_ids)
    bookkeeping = [r for r in report["results"] if r["id"] == "bookkeeping"]
    assert bookkeeping and bookkeeping[0]["status"] == "MATCH"


def test_german_campaigns_count_as_campaign_management(embedder):
    report = _report("marketing_en_content", "marketing_de_managerin", embedder)
    campaign = [r for r in report["results"] if r["id"] == "campaign_management"]
    assert campaign and campaign[0]["status"] == "MATCH"


def test_mixed_enumeration_keeps_single_words():
    items = _short_list_items("Empathetic, reliable and responsible team player.")
    assert items == ["Empathetic", "reliable"]


def test_single_item_sentence_is_not_split():
    assert _short_list_items("Responsible team player.") == []
