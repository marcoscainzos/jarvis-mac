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
    assert pattern.feed(130, 2.5) is False
