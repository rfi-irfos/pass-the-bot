from passthebot.normalizer import ExtractedKeyword
from passthebot.requirement import classify_importance, detect_required_ids

PYTHON_KW = ExtractedKeyword(id="python", category="languages", matched_text="Python", confidence=1.0)
DOCKER_KW = ExtractedKeyword(id="docker", category="tools", matched_text="Docker", confidence=1.0)


def test_required_signal_marks_id_required():
    text = "Python is required for this role."
    result = detect_required_ids(text, [PYTHON_KW])
    assert result == {"python"}


def test_optional_signal_marks_id_not_required():
    text = "Docker experience is nice to have."
    result = detect_required_ids(text, [DOCKER_KW])
    assert result == set()


def test_no_signal_defaults_to_required():
    text = "We use Python extensively across our stack."
    result = detect_required_ids(text, [PYTHON_KW])
    assert result == {"python"}


def test_german_signal_phrases_recognized():
    required_text = "Python-Kenntnisse sind zwingend erforderlich."
    assert detect_required_ids(required_text, [PYTHON_KW]) == {"python"}

    optional_text = "Docker-Erfahrung ist von Vorteil, aber kein Muss."
    assert detect_required_ids(optional_text, [DOCKER_KW]) == set()


def test_multiple_mentions_required_signal_wins_if_seen_once():
    text = "Docker is nice to have for most tasks, but Docker is required for deployment."
    result = detect_required_ids(text, [DOCKER_KW])
    assert result == {"docker"}


def test_multiple_keywords_independent_classification():
    text = "Python is required. Docker experience is nice to have."
    result = detect_required_ids(text, [PYTHON_KW, DOCKER_KW])
    assert result == {"python"}


def _kw(id_, text, mentions=None):
    return ExtractedKeyword(
        id=id_, category="tools", matched_text=text, confidence=1.0, mentions=mentions or [text]
    )


# Shaped like the posting in GitHub issue #13: skills named in the company
# intro, with a real requirements section further down.
ISSUE_13_POSTING = """Backed by top investors, from our first German seed to SAP's recent investment.
Earned 190K+ GitHub stars.

REQUIREMENTS
Must-haves
- Python experience
- Docker

Nice-to-haves
- Terraform

Why join us?
You will work with Kubernetes people.
"""


def test_company_intro_mentions_are_not_requirements():
    keywords = [_kw("german", "German"), _kw("sap", "SAP"), _kw("github", "GitHub")]
    assert detect_required_ids(ISSUE_13_POSTING, keywords) == set()
    levels = classify_importance(ISSUE_13_POSTING, keywords)
    assert {k: v.level for k, v in levels.items()} == {
        "german": "mentioned", "sap": "mentioned", "github": "mentioned",
    }


def test_section_decides_required_vs_optional():
    keywords = [_kw("python", "Python"), _kw("terraform", "Terraform"), _kw("kubernetes", "Kubernetes")]
    levels = classify_importance(ISSUE_13_POSTING, keywords)
    assert levels["python"].level == "required"
    assert levels["terraform"].level == "optional"
    assert levels["kubernetes"].level == "mentioned"


def test_evidence_quotes_the_line_that_decided_the_level():
    levels = classify_importance(ISSUE_13_POSTING, [_kw("github", "GitHub"), _kw("terraform", "Terraform")])
    assert levels["github"].evidence == "Earned 190K+ GitHub stars."
    assert levels["terraform"].evidence == "Terraform"


def test_long_evidence_is_shortened_on_a_word_boundary():
    posting = "Requirements\n- Python " + "and many other things " * 20
    evidence = classify_importance(posting, [_kw("python", "Python")])["python"].evidence
    assert len(evidence) <= 161
    assert evidence.endswith("…")
    assert not evidence[:-1].endswith(" ")


def test_highest_level_wins_across_mentions():
    posting = "We love Docker.\n\nRequirements\n- Docker\n"
    assert classify_importance(posting, [_kw("docker", "Docker")])["docker"].level == "required"


def test_any_alias_can_decide_the_level():
    posting = "Unser Team spricht Deutsch.\n\nRequirements\n- Fluent German\n"
    keyword = _kw("german", "Deutsch", mentions=["Deutsch", "German"])
    assert classify_importance(posting, [keyword])["german"].level == "required"


def test_signal_phrase_overrides_its_section():
    posting = "Requirements\n- Docker is a bonus\n\nAbout us\nPython is required here.\n"
    levels = classify_importance(posting, [_kw("docker", "Docker"), _kw("python", "Python")])
    assert levels["docker"].level == "optional"
    assert levels["python"].level == "required"


def test_short_alias_only_matches_whole_words():
    posting = "Requirements\n- Good communication\n\nAbout us\nWe go far.\n"
    # "go" must count from "We go far", not from inside "Good".
    assert classify_importance(posting, [_kw("go", "Go")])["go"].level == "mentioned"


def test_posting_without_sections_keeps_required_default():
    posting = "We use Python extensively. Docker is nice to have."
    levels = classify_importance(posting, [_kw("python", "Python"), _kw("docker", "Docker")])
    assert levels["python"].level == "required"
    assert levels["docker"].level == "optional"


def test_keyword_not_found_in_text_falls_back_to_required():
    levels = classify_importance("Requirements\n- Python\n", [_kw("teamwork", "works well in teams")])
    assert levels["teamwork"].level == "required"
    assert levels["teamwork"].evidence is None
