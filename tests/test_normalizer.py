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


JAVA_ENTRIES = [
    SkillEntry(
        id="java", category="languages", display={"en": "Java"},
        status="curated", added="2026-09-14",
        aliases=["Java", "java"],
    ),
    SkillEntry(
        id="javascript", category="languages", display={"en": "JavaScript"},
        status="curated", added="2026-09-14",
        aliases=["JavaScript", "Javascript", "javascript", "JS", "js"],
    ),
]


def test_javascript_mention_does_not_falsely_match_java():
    result = extract_discrete_keywords("We use JavaScript extensively.", JAVA_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"javascript"}
    assert "java" not in ids


CPLUSPLUS_ENTRIES = [
    SkillEntry(
        id="cplusplus", category="languages", display={"en": "C++"},
        status="curated", added="2026-09-14",
        aliases=["C++", "c++"],
    ),
]


def test_matches_alias_ending_in_punctuation():
    result = extract_discrete_keywords("Experience with C++ required.", CPLUSPLUS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"cplusplus"}


NODEJS_JS_ENTRIES = [
    SkillEntry(
        id="nodejs", category="languages", display={"en": "Node.js"},
        status="curated", added="2026-09-14",
        aliases=["Node.js", "Node", "NodeJS", "nodejs", "node js"],
    ),
    SkillEntry(
        id="javascript", category="languages", display={"en": "JavaScript"},
        status="curated", added="2026-09-14",
        aliases=["JavaScript", "Javascript", "javascript", "JS", "js"],
    ),
]


def test_nodejs_punctuation_normalization_does_not_falsely_match_javascript():
    """Regression test: normalize_string rewrites '.' to a space, so "Node.js"
    normalizes to "node js". Without span-claiming, the short "js" alias
    (owned by javascript) would also match inside that normalized text via
    the boundary regex, incorrectly extracting javascript alongside nodejs.
    Longest-alias-first matching with span-claiming must let "node js" claim
    that text region before "js" gets a chance to match inside it.
    """
    result = extract_discrete_keywords("We use Node.js in production.", NODEJS_JS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"nodejs"}
    assert "javascript" not in ids


def test_javascript_alone_still_matches_when_nodejs_not_present():
    result = extract_discrete_keywords("We use JS extensively.", NODEJS_JS_ENTRIES)
    ids = {r.id for r in result}
    assert ids == {"javascript"}
