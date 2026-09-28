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


def test_bulleted_resume_does_not_skew_word_length_metrics():
    # Bullets and dashes alone should not be counted as words, preventing
    # deflation of avg_word_length_chars in the most common resume format.
    bulleted_text = "Skills\n- Python\n- Docker\n- Kubernetes and container orchestration"
    result_bulleted = compute_readability(bulleted_text)

    # The same content without bullets should have the same avg_word_length_chars.
    unbulleted_text = "Skills Python Docker Kubernetes and container orchestration"
    result_unbulleted = compute_readability(unbulleted_text)

    # Both should compute the same metric since "-" tokens strip to zero length
    # and should not count as words.
    assert result_bulleted.avg_word_length_chars == result_unbulleted.avg_word_length_chars
    # Verify the metric is reasonable (not skewed low by bullets).
    assert result_bulleted.avg_word_length_chars > 4.0
