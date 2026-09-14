from passthebot.embeddings import Embedder
from passthebot.graph import SkillEntry
from passthebot.normalizer import extract_soft_skills

SOFT_SKILL_ENTRIES = [
    SkillEntry(
        id="teamwork", category="soft_skills", display={"en": "Team player"},
        status="curated", added="2026-09-14",
        anchor_phrases=["team player", "works well in teams", "collaborative"],
        embedding_threshold=0.45,
    ),
]


def test_embedder_scores_similar_phrases_higher():
    embedder = Embedder()
    high = embedder.best_match("great team player who collaborates well", ["team player"])
    low = embedder.best_match("expert in database indexing", ["team player"])
    assert high[1] > low[1]


def test_extract_soft_skills_matches_close_phrase():
    embedder = Embedder()
    result = extract_soft_skills(
        "Looking for someone who works well in teams.", SOFT_SKILL_ENTRIES, embedder
    )
    assert len(result) == 1
    assert result[0].id == "teamwork"
    assert result[0].confidence >= 0.45


def test_extract_soft_skills_below_threshold_excluded():
    embedder = Embedder()
    result = extract_soft_skills(
        "We build embedded firmware for industrial sensors.", SOFT_SKILL_ENTRIES, embedder
    )
    assert result == []
