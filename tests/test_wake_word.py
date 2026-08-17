from jarvis.wake_word import command_after_wake_word, contains_sleep_word


def test_detects_iris_alone() -> None:
    assert command_after_wake_word("Iris") == ""


def test_extracts_command_after_iris() -> None:
    assert command_after_wake_word("Iris, abre Safari") == "abre safari"


def test_accepts_common_whisper_variant() -> None:
    assert command_after_wake_word("Hiris pon musica") == "pon musica"
    assert command_after_wake_word("Iriz abre Safari") == "abre safari"


def test_ignores_other_sounds_and_speech() -> None:
    assert command_after_wake_word("hola, abre Safari") is None


def test_detects_global_sleep_word() -> None:
    assert contains_sleep_word("Iris, duerme")
    assert contains_sleep_word("DUERME")
    assert contains_sleep_word("dueme")
    assert contains_sleep_word("duermete")
    assert contains_sleep_word("durme")
    assert not contains_sleep_word("puedes ayudarme")
