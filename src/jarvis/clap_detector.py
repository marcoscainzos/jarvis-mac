from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class DoubleClapPattern:
    """Reconoce dos picos separados sin almacenar muestras de audio."""

    def __init__(
        self,
        threshold: int = 9_000,
        min_gap: float = 0.12,
        max_gap: float = 0.85,
    ) -> None:
        self.threshold = threshold
        self.release_threshold = int(threshold * 0.55)
        self.min_gap = min_gap
        self.max_gap = max_gap
        self._last_clap: float | None = None
        self._above_threshold = False

    def feed(self, peak: int, now: float) -> bool:
        if peak <= self.release_threshold:
            self._above_threshold = False
            return False
        if peak < self.threshold or self._above_threshold:
            return False

        self._above_threshold = True
        if self._last_clap is None:
            self._last_clap = now
            return False

        gap = now - self._last_clap
        self._last_clap = None if self.min_gap <= gap <= self.max_gap else now
        return self.min_gap <= gap <= self.max_gap


class ClapDetector:
    def __init__(
        self,
        on_double_clap: Callable[[], None],
        pattern: DoubleClapPattern | None = None,
    ) -> None:
        self.on_double_clap = on_double_clap
        self.pattern = pattern or DoubleClapPattern()
        self.stream: Any = None
        self.paused = False

    def start(self) -> None:
        if self.stream is not None:
            return
        import sounddevice as sd

        self.stream = sd.InputStream(
            samplerate=16_000,
            channels=1,
            dtype="int16",
            blocksize=800,
            callback=self._audio_callback,
        )
        self.stream.start()

    def stop(self) -> None:
        if self.stream is None:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None

    def pause(self) -> None:
        self.paused = True

    def resume(self) -> None:
        self.paused = False

    def _audio_callback(
        self, indata: Any, _frames: int, _time_info: Any, _status: Any
    ) -> None:
        if self.paused:
            return
        peak = int(abs(indata).max())
        if self.pattern.feed(peak, time.monotonic()):
            self.paused = True
            self.on_double_clap()
