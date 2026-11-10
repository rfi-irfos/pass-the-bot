"""Proposed (ai-suggested-pending) skills: inert until a human approves them.

The postings in tests/data/postings_pending/ are synthetic. They are matched
against the graph *including* pending entries to show what the proposed batch
would do once reviewed; the normal pipeline must not see those entries yet.
"""

from pathlib import Path

import pytest
import yaml

from passthebot.graph import DEFAULT_DATA_DIR, active_entries, load_skill_graph
from passthebot.normalizer import extract_discrete_keywords

DATA = Path(__file__).parent / "data"
PENDING_POSTINGS = sorted((DATA / "postings_pending").glob("*.txt"))
CURATED_POSTINGS = sorted((DATA / "postings").glob("*.txt"))
GRAPH = load_skill_graph(DEFAULT_DATA_DIR)
PENDING_IDS = {e.id for e in GRAPH if e.status == "ai-suggested-pending"}


def _found(text: str, entries) -> set[str]:
    return {k.id for k in extract_discrete_keywords(text, entries)}


def test_pending_entries_are_ignored_by_normal_matching():
    assert PENDING_IDS
    assert PENDING_IDS.isdisjoint({e.id for e in active_entries(GRAPH)})


@pytest.mark.parametrize("posting", PENDING_POSTINGS, ids=lambda p: p.stem)
def test_pending_skills_are_found_once_approved(posting):
    gold = yaml.safe_load(posting.with_suffix(".expected.yaml").read_text())
    found = _found(posting.read_text(), GRAPH)
    assert set(gold["expected"]) - found == set()
    assert set(gold["forbidden"]) & found == set()


@pytest.mark.parametrize("posting", CURATED_POSTINGS, ids=lambda p: p.stem)
def test_pending_skills_add_no_false_hits_to_existing_postings(posting):
    """The proposals cover other occupations; none may fire on the curated benchmark."""
    gold = yaml.safe_load(posting.with_suffix(".expected.yaml").read_text())
    allowed = set(gold.get("pending_ok", []))  # real requirements the proposals rightly find
    assert _found(posting.read_text(), GRAPH) & PENDING_IDS - allowed == set()


def test_recruiter_byline_does_not_give_every_linkedin_ad_a_recruiting_skill():
    """The poster's title ('Talent Acquisition Partner') and 'Currently recruiting for ...'
    sit in the page header of LinkedIn ads; they say nothing about the job."""
    byline = "Talent Acquisition Partner Nursing, Specialist in Nurse Recruitment. Currently recruiting for a ward."
    assert "recruiting" not in _found(byline, GRAPH)
