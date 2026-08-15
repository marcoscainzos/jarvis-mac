from jarvis.audio import Listener, Speaker, SpeechError, UnrecognizedSpeech


class FakeListener:
    def listen(self) -> str:
        return "hola Jarvis"


class FakeSpeaker:
    def speak(self, message: str) -> None:
        self.last_message = message


def test_audio_adapters_are_replaceable() -> None:
    listener: Listener = FakeListener()
    speaker: Speaker = FakeSpeaker()

    speaker.speak(listener.listen())

    assert speaker.last_message == "hola Jarvis"


def test_unrecognized_speech_is_a_recoverable_voice_error() -> None:
    assert issubclass(UnrecognizedSpeech, SpeechError)
