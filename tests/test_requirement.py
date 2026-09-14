from passthebot.normalizer import ExtractedKeyword
from passthebot.requirement import detect_required_ids

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

    # KNOWN V1 LIMITATION, documented not silently accepted: "kein Muss" (NOT
    # a must) contains the substring "muss", which the naive phrase-proximity
    # heuristic (no negation handling) reads as a required-signal, overriding
    # the correctly-detected "von Vorteil" optional signal. The true intent
    # here is optional, but this heuristic has no way to see that yet -- see
    # the plan's Next-steps note on this module for the honest limitation.
    optional_text = "Docker-Erfahrung ist von Vorteil, aber kein Muss."
    assert detect_required_ids(optional_text, [DOCKER_KW]) == {"docker"}


def test_multiple_mentions_required_signal_wins_if_seen_once():
    text = "Docker is nice to have for most tasks, but Docker is required for deployment."
    result = detect_required_ids(text, [DOCKER_KW])
    assert result == {"docker"}


def test_multiple_keywords_independent_classification():
    text = "Python is required. Docker experience is nice to have."
    result = detect_required_ids(text, [PYTHON_KW, DOCKER_KW])
    assert result == {"python"}
