from jarvis.clap_detector import DoubleClapPattern


def test_detects_two_separate_claps() -> None:
    pattern = DoubleClapPattern(threshold=100)
    assert pattern.feed(120, 1.0) is False
    assert pattern.feed(0, 1.05) is False
    assert pattern.feed(130, 1.5) is True


def test_rejects_long_gap_and_sustained_noise() -> None:
    pattern = DoubleClapPattern(threshold=100)
    assert pattern.feed(120, 1.0) is False
    assert pattern.feed(130, 1.1) is False
    assert pattern.feed(0, 1.2) is False
    assert pattern.feed(130, 2.6) is False


def test_adapts_threshold_to_background_noise() -> None:
    pattern = DoubleClapPattern(threshold=100)
    for index in range(40):
        pattern.feed(60, index * 0.05)
    assert pattern.current_threshold > 100
    assert pattern.feed(120, 3.0) is False


def test_voice_peaks_do_not_permanently_raise_clap_threshold() -> None:
    pattern = DoubleClapPattern(threshold=700)
    for index in range(30):
        pattern.feed(650, index * 0.05)
    for index in range(30, 70):
        pattern.feed(40, index * 0.05)

    assert pattern.current_threshold == 700
    assert pattern.feed(800, 4.0) is False
    assert pattern.feed(0, 4.1) is False
    assert pattern.feed(850, 4.6) is True
