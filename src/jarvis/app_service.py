from __future__ import annotations

from jarvis.assistant import Assistant, Reply
from jarvis.audio import Listener, Speaker


class JarvisService:
    """Une voz y cerebro sin depender de ninguna interfaz gráfica."""

    def __init__(
        self, assistant: Assistant, listener: Listener, speaker: Speaker
    ) -> None:
        self.assistant = assistant
        self.listener = listener
        self.speaker = speaker

    def listen_and_reply(self) -> tuple[str, Reply]:
        command = self.listener.listen()
        reply = self.assistant.handle(command)
        self.speaker.speak(reply.message)
        return command, reply
