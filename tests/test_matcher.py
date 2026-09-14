from passthebot.matcher import match
from passthebot.normalizer import ExtractedKeyword

POSTING = [
    ExtractedKeyword(id="python", category="languages", matched_text="Python", confidence=1.0),
    ExtractedKeyword(id="docker", category="tools", matched_text="Docker", confidence=1.0),
    ExtractedKeyword(id="react", category="frameworks", matched_text="React", confidence=1.0),
]


def test_exact_match_when_resume_has_same_id():
    resume = [ExtractedKeyword(id="python", category="languages", matched_text="python", confidence=1.0)]
    results = match(POSTING, resume, required_ids={"python"})
    python_result = next(r for r in results if r.id == "python")
    assert python_result.status == "MATCH"
    assert python_result.required is True


def test_missing_when_resume_lacks_id_and_no_fuzzy_hit():
    results = match(POSTING, [], required_ids={"python", "docker", "react"})
    statuses = {r.id: r.status for r in results}
    assert statuses["python"] == "MISSING"
    assert statuses["docker"] == "MISSING"
    assert statuses["react"] == "MISSING"


def test_required_flag_reflects_input():
    results = match(POSTING, [], required_ids={"python"})
    by_id = {r.id: r for r in results}
    assert by_id["python"].required is True
    assert by_id["docker"].required is False


def test_java_does_not_match_javascript():
    posting = [ExtractedKeyword(id="javascript", category="languages", matched_text="JavaScript", confidence=1.0)]
    resume = [ExtractedKeyword(id="java", category="languages", matched_text="Java", confidence=1.0)]
    results = match(posting, resume, required_ids={"javascript"})
    assert results[0].status == "MISSING"
