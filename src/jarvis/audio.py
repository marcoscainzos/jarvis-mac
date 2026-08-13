from __future__ import annotations

from typing import Protocol


class Listener(Protocol):
    def listen(self) -> str: ...


class Speaker(Protocol):
    def speak(self, message: str) -> None: ...


class SpeechError(RuntimeError):
    """Error recuperable del sistema de voz."""

