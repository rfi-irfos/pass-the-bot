from unittest.mock import patch

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

SOFT_SKILL_NO_THRESHOLD = [
    SkillEntry(
        id="leadership", category="soft_skills", display={"en": "Leader"},
        status="curated", added="2026-09-14",
        anchor_phrases=["leader", "leadership", "leads teams"],
        # embedding_threshold intentionally omitted to test None fallback
    ),
]


def test_embedder_caches_phrase_embeddings_across_calls():
    """Real-world perf bug: best_match re-encoded the (static, curated)
    anchor-phrase list on every single call. With N sentences x M soft-skill
    entries per request, that's N*M redundant model forward passes on a
    fixed, never-changing input -- observed as 3-15s per /api/check request
    in production. Phrase embeddings must be cached by phrase-list content."""
    embedder = Embedder()
    phrases = ["team player", "collaborative"]
    with patch.object(embedder._model, "encode", wraps=embedder._model.encode) as mock_encode:
        embedder.best_match("great team player", phrases)
        embedder.best_match("another sentence entirely", phrases)
        phrase_encode_calls = [
            c for c in mock_encode.call_args_list if c.args and c.args[0] == phrases
        ]
        assert len(phrase_encode_calls) == 1


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


def test_extract_soft_skills_uses_0_48_default_when_threshold_not_set():
    """Verify that entries without embedding_threshold explicitly set fall back to 0.48 default.

    Raised from the original 0.45 placeholder (2026-09-14) after real-CV testing with a
    fuller soft-skill graph (6 entries instead of 1) surfaced two borderline false positives
    at 0.45-0.47 (problem_solving/analytical_thinking matching an unrelated regulatory-text
    fragment) sitting right next to a genuine match at 0.49 (communication). 0.48 keeps the
    genuine match, rejects the two false positives. Still not a full calibration harness
    (see the plan's Next-steps note) — just an evidence-based nudge from a real n=1 test.
    """
    embedder = Embedder()
    # This should match because the similarity to "leader" exceeds 0.48 default
    result = extract_soft_skills(
        "We need a strong leader to guide the organization.", SOFT_SKILL_NO_THRESHOLD, embedder
    )
    assert len(result) == 1
    assert result[0].id == "leadership"
    assert result[0].confidence >= 0.48


def test_extract_soft_skills_finds_signal_diluted_in_multi_sentence_document():
    """Regression test for the whole-document embedding dilution bug (Task 8).

    Embedding the entire multi-sentence text as a single vector dilutes a strong
    soft-skill mention down below threshold once it's surrounded by unrelated
    filler sentences (observed: 0.20-0.26 vs. 0.56-0.72 for the sentence alone).
    extract_soft_skills must score each sentence independently and keep the max,
    so the "teamwork" mention is still found even buried in a realistic
    multi-sentence posting/resume.
    """
    embedder = Embedder()
    text = (
        "Our company builds industrial sensors for the automotive sector. "
        "We are headquartered in Linz and have offices across Europe. "
        "The ideal candidate works well in teams and communicates clearly. "
        "Benefits include a company car and flexible working hours. "
        "Applications close at the end of the month."
    )
    result = extract_soft_skills(text, SOFT_SKILL_ENTRIES, embedder)
    assert len(result) == 1
    assert result[0].id == "teamwork"
    assert result[0].confidence >= 0.45


def test_extract_soft_skills_finds_signal_in_bullet_list_without_terminal_punctuation():
    """Regression test: real job postings are commonly bullet lists with no
    terminal punctuation per line. split_sentences must split on newlines too,
    not just on . ! ? , or the whole bullet list collapses into one fragment
    and reintroduces the whole-document dilution bug (Task 8) for this format.
    """
    embedder = Embedder()
    text = (
        "Anforderungen:\n"
        "- Python\n"
        "- Teamfaehigkeit und gute Kommunikation, arbeitet gut im Team\n"
        "- Docker\n"
        "- Reisebereitschaft"
    )
    result = extract_soft_skills(text, SOFT_SKILL_ENTRIES, embedder)
    assert len(result) == 1
    assert result[0].id == "teamwork"
    assert result[0].confidence >= 0.45
