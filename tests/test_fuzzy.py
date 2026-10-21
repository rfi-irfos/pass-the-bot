from passthebot.fuzzy import fuzzy_best_match


def test_close_typo_matches_above_threshold():
    result = fuzzy_best_match("dockr", ["Docker", "Kubernetes"])
    assert result is not None
    candidate, score = result
    assert candidate == "Docker"
    assert score >= 0.75


def test_unrelated_term_returns_none():
    result = fuzzy_best_match("banana", ["Docker", "Kubernetes"])
    assert result is None


def test_exact_match_scores_1():
    result = fuzzy_best_match("Docker", ["Docker", "Kubernetes"])
    assert result == ("Docker", 1.0)


def test_long_shared_ending_is_not_a_typo():
    """German compounds share long endings: "Finanzbuchhaltung" scores 0.81
    against "Lohnbuchhaltung" but differs in five letters, so it's a
    different skill, not a typo."""
    assert fuzzy_best_match("Finanzbuchhaltung", ["Lohnbuchhaltung"]) is None


def test_transposed_letters_are_still_a_typo():
    assert fuzzy_best_match("Pyhton", ["Python"]) is not None
