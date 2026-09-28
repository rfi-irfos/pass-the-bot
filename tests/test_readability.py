from passthebot.readability import compute_readability


def test_short_simple_sentences_score_near_the_maximum():
    text = "The cat sat on the mat. It was warm and cozy inside the house today."
    result = compute_readability(text)
    assert result.score == 100.0
    assert result.avg_words_per_sentence == 7.5


def test_long_complex_sentences_score_near_the_minimum():
    text = (
        "Notwithstanding the aforementioned circumstances, the multifaceted "
        "implementation necessitated comprehensive reconsideration of the "
        "previously established methodological framework. Consequently, "
        "stakeholders recommended substantial reorganization of the "
        "interdisciplinary collaborative infrastructure."
    )
    result = compute_readability(text)
    assert result.score == 0.0
    assert result.grade_level > 20


def test_too_short_text_returns_none_score_but_keeps_raw_counts():
    result = compute_readability("Python.")
    assert result.score is None
    assert result.grade_level is None
    assert result.avg_words_per_sentence == 1.0
    assert result.avg_word_length_chars == 6.0


def test_punctuation_attached_to_words_does_not_inflate_length():
    # "cat," and "cat" must count as the same length for this metric.
    result = compute_readability("The cat, the dog, and the bird all played. They ran around the yard together.")
    assert result.avg_word_length_chars < 4.0
