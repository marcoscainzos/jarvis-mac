from jarvis.app_service import JarvisService
from jarvis.assistant import Assistant


class FakeListener:
    def listen(self) -> str:
        return "¿Qué puedes hacer?"


class FakeSpeaker:
    def __init__(self) -> None:
        self.messages: list[str] = []

    def speak(self, message: str) -> None:
        self.messages.append(message)


def test_service_connects_listener_assistant_and_speaker() -> None:
    speaker = FakeSpeaker()
    service = JarvisService(
        Assistant(lambda _: False), FakeListener(), speaker
    )

    command, reply = service.listen_and_reply()

    assert command == "¿Qué puedes hacer?"
    assert reply.message.startswith("Puedo conversar")
    assert speaker.messages == [reply.message]
