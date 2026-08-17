from __future__ import annotations

import re
import threading
import unicodedata
from collections.abc import Callable

from jarvis.audio import NoSpeechTimeout, SpeechError, UnrecognizedSpeech
from jarvis.speech import LocalWhisperListener


def command_after_wake_word(transcript: str) -> str | None:
    """Devuelve lo dicho tras Jarvis, o None si no se pronuncio la palabra."""
    normalized = unicodedata.normalize("NFKD", transcript.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    # Whisper puede escribir el nombre foneticamente de varias formas en espanol.
    match = re.search(
        r"\b(?:jarvis|yarvis|harvis|charvis|llervis|allervis)\b[\s,.:;!?-]*(.*)",
        normalized,
    )
    return match.group(1).strip() if match else None


class WakeWordDetector:
    """Escucha frases localmente y activa Jarvis solo al oir su nombre."""

    def __init__(
        self,
        listener: LocalWhisperListener,
        on_wake: Callable[[str], None],
    ) -> None:
        self.listener = listener
        self.on_wake = on_wake
        self._stop = threading.Event()
        self._enabled = threading.Event()
        self._thread: threading.Thread | None = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        self._stop.clear()
        self._enabled.set()
        if self.running:
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._enabled.clear()
        self._stop.set()

    def pause(self) -> None:
        self._enabled.clear()

    def resume(self) -> None:
        if not self._stop.is_set():
            self._enabled.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            self._enabled.wait(0.25)
            if not self._enabled.is_set() or self._stop.is_set():
                continue
            try:
                transcript = self.listener.listen(
                    wait_timeout=1.0,
                    notify_recorded=False,
                )
            except (NoSpeechTimeout, UnrecognizedSpeech, SpeechError):
                continue
            command = command_after_wake_word(transcript)
            if command is None:
                continue
            self.pause()
            self.on_wake(command)
