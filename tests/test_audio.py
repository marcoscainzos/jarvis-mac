from jarvis.audio import Listener, Speaker


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
