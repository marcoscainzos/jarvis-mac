from jarvis.voice_benchmark import normalize_words, word_error_rate


def test_normalizes_spanish_text_for_voice_metrics() -> None:
    assert normalize_words("¡Iris, qué tal!") == ["iris", "que", "tal"]


def test_word_error_rate_is_zero_for_equivalent_text() -> None:
    assert word_error_rate("Iris, abre Safari", "iris abre safari") == 0.0


def test_word_error_rate_counts_substitution_and_missing_word() -> None:
    assert word_error_rate("iris abre ahora safari", "iris abre chrome") == 0.5
