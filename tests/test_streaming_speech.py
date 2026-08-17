from jarvis.macos_speech import MacOSSpeaker


class RecordingSpeaker(MacOSSpeaker):
    def __init__(self) -> None:
        super().__init__()
        self.messages: list[str] = []

    def speak(self, message: str) -> None:
        self.messages.append(message)


def test_speaks_complete_sentences_while_text_arrives() -> None:
    speaker = RecordingSpeaker()
    speaker.begin_stream()
    speaker.feed_stream_chunk("Primera frase. Segu")
    speaker.feed_stream_chunk("nda frase. Final")
    assert speaker.finish_stream()
    assert speaker.messages == ["Primera frase.", "Segunda frase.", "Final"]


def test_empty_stream_falls_back_to_normal_reply() -> None:
    speaker = RecordingSpeaker()
    speaker.begin_stream()
    assert not speaker.finish_stream()
