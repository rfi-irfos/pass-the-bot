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
