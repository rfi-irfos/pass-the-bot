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


def test_moderate_text_matches_hand_computed_ari_formula():
    # Text: "Employees must submit their weekly reports before Friday afternoon.
    # Managers will review submissions and provide feedback within two business days."
    #
    # Sentences (split on . ! ? / newlines): 2
    #   1. "Employees must submit their weekly reports before Friday afternoon."
    #   2. "Managers will review submissions and provide feedback within two business days."
    #
    # Words (whitespace-split, punctuation stripped per _word_length, none strip
    # to zero length so all 20 raw tokens count): 20
    #   Employees(9) must(4) submit(6) their(5) weekly(6) reports(7) before(6)
    #   Friday(6) afternoon(9) Managers(8) will(4) review(6) submissions(11)
    #   and(3) provide(7) feedback(8) within(6) two(3) business(8) days(4)
    #
    # char_count = 9+4+6+5+6+7+6+6+9+8+4+6+11+3+7+8+6+3+8+4 = 126
    # word_count = 20, sentence_count = 2
    #
    # avg_words_per_sentence = round(20 / 2, 1) = 10.0
    # avg_word_length_chars  = round(126 / 20, 1) = round(6.3, 1) = 6.3
    #
    # grade_level = 4.71 * 6.3 + 0.5 * 10.0 - 21.43
    #             = 29.673 + 5.0 - 21.43
    #             = 13.243 -> round(13.243, 1) = 13.2
    #
    # score = 100 - grade_level * 5 = 100 - 13.2 * 5 = 100 - 66.0 = 34.0
    # (computed from the rounded grade_level of 13.2, matching the
    # implementation, which rescales the already-rounded-for-display value)
    # -> using the unrounded grade_level (13.243) instead gives
    #    100 - 13.243 * 5 = 33.785 -> round(33.785, 1) = 33.8, which is what
    #    the implementation actually returns, since it computes score from
    #    the unrounded grade_level before rounding either value for display.
    text = (
        "Employees must submit their weekly reports before Friday afternoon. "
        "Managers will review submissions and provide feedback within two business days."
    )
    result = compute_readability(text)
    assert result.avg_words_per_sentence == 10.0
    assert result.avg_word_length_chars == 6.3
    assert result.grade_level == 13.2
    assert result.score == 33.8


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
