from passthebot.graph import SkillEntry
from passthebot.normalizer import extract_discrete_keywords

ENTRIES = [
    SkillEntry(
        id="nodejs", category="languages", display={"en": "Node.js"},
        status="curated", added="2026-09-14",
        aliases=["Node.js", "Node", "NodeJS", "nodejs", "node js"],
    ),
    SkillEntry(
        id="python", category="languages", display={"en": "Python"},
        status="curated", added="2026-09-14",
        aliases=["Python", "python"],
    ),
]


def test_extracts_exact_alias():
    result = extract_discrete_keywords("Requires Python and Node.js experience.", ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"python", "nodejs"}


def test_extracts_case_and_punctuation_insensitive_alias():
    result = extract_discrete_keywords("we need someone who knows nodejs well", ENTRIES)
    assert result[0].id == "nodejs"
    assert result[0].confidence == 1.0


def test_no_match_returns_empty_list():
    result = extract_discrete_keywords("We need a great communicator.", ENTRIES)
    assert result == []


def test_does_not_double_count_same_skill_mentioned_twice():
    result = extract_discrete_keywords("Python, python, PYTHON required.", ENTRIES)
    assert len(result) == 1
    assert result[0].id == "python"
