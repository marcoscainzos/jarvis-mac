from jarvis.wake_word import command_after_wake_word, contains_sleep_word


def test_detects_jarvis_alone() -> None:
    assert command_after_wake_word("Jarvis") == ""


def test_extracts_command_after_jarvis() -> None:
    assert command_after_wake_word("Jarvis, abre Safari") == "abre safari"


def test_accepts_common_whisper_variant() -> None:
    assert command_after_wake_word("Allervis pon musica") == "pon musica"


def test_ignores_other_sounds_and_speech() -> None:
    assert command_after_wake_word("hola, abre Safari") is None


def test_detects_global_sleep_word() -> None:
    assert contains_sleep_word("Jarvis, duerme")
    assert contains_sleep_word("DUERME")
    assert not contains_sleep_word("puedes ayudarme")
