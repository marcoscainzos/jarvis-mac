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
        r"\b(?:jarvis|yarvis|harvis|charvis|llervis|allervis|jervis|jarbis|jarviz|arvis)\b[\s,.:;!?-]*(.*)",
        normalized,
    )
    if match:
        return match.group(1).strip()

    # Tolera hasta dos letras distintas en una palabra de longitud parecida.
    words = list(re.finditer(r"\b[a-z]{4,7}\b", normalized))
    for word in words:
        if _edit_distance(word.group(), "jarvis") <= 2:
            return normalized[word.end():].lstrip(" ,.:;!?-")
    return None


def _edit_distance(left: str, right: str) -> int:
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, start=1):
        current = [index]
        for other_index, right_char in enumerate(right, start=1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[other_index] + 1,
                    previous[other_index - 1] + (left_char != right_char),
                )
            )
        previous = current
    return previous[-1]


def contains_sleep_word(transcript: str) -> bool:
    normalized = unicodedata.normalize("NFKD", transcript.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.search(r"\bduerme\b", normalized) is not None


class WakeWordDetector:
    """Escucha frases localmente y activa Jarvis solo al oir su nombre."""

    def __init__(
        self,
        listener: LocalWhisperListener,
        on_wake: Callable[[str], None],
        on_sleep: Callable[[], None] | None = None,
    ) -> None:
        self.listener = listener
        self.on_wake = on_wake
        self.on_sleep = on_sleep
        self._stop = threading.Event()
        self._enabled = threading.Event()
        self._thread: threading.Thread | None = None
        self._sleep_only = False

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
            self._sleep_only = False
            self._enabled.set()

    def listen_for_sleep(self) -> None:
        """Durante una interacción ignora todo excepto la orden «duerme»."""
        if not self._stop.is_set():
            self._sleep_only = True
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
                    wake_mode=True,
                )
            except (NoSpeechTimeout, UnrecognizedSpeech, SpeechError):
                continue
            if contains_sleep_word(transcript):
                self.pause()
                if self.on_sleep is not None:
                    self.on_sleep()
                continue
            if self._sleep_only:
                continue
            command = command_after_wake_word(transcript)
            if command is None:
                continue
            self.pause()
            self.on_wake(command)
