from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any


class DoubleClapPattern:
    """Reconoce dos picos separados sin almacenar muestras de audio."""

    def __init__(
        self,
        threshold: int = 1_800,
        min_gap: float = 0.08,
        max_gap: float = 1.50,
    ) -> None:
        self.minimum_threshold = threshold
        self.noise_floor = max(5.0, threshold / 10)
        self.min_gap = min_gap
        self.max_gap = max_gap
        self._last_clap: float | None = None
        self._above_threshold = False

    def feed(self, peak: int, now: float) -> bool:
        threshold = self.current_threshold
        release_threshold = max(
            int(self.minimum_threshold * 0.40), int(self.noise_floor * 1.8)
        )
        if peak <= release_threshold:
            self._above_threshold = False
            self._update_noise_floor(peak)
            return False
        if peak < threshold:
            self._update_noise_floor(peak)
            return False
        if self._above_threshold:
            return False

        self._above_threshold = True
        if self._last_clap is None:
            self._last_clap = now
            return False

        gap = now - self._last_clap
        self._last_clap = None if self.min_gap <= gap <= self.max_gap else now
        return self.min_gap <= gap <= self.max_gap

    @property
    def current_threshold(self) -> int:
        return max(self.minimum_threshold, int(self.noise_floor * 4.2))

    def _update_noise_floor(self, peak: int) -> None:
        self.noise_floor = self.noise_floor * 0.96 + peak * 0.04

    def reset(self) -> None:
        self._last_clap = None
        self._above_threshold = False


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
        self._blocked_until = 0.0

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
        # Ignora sonidos de arranque y deja estabilizar el nivel del micrófono.
        self.pattern.reset()
        self._blocked_until = time.monotonic() + 5.0

    def stop(self) -> None:
        if self.stream is None:
            return
        self.stream.stop()
        self.stream.close()
        self.stream = None

    def pause(self) -> None:
        self.paused = True

    def resume(self, cooldown: float = 0.0) -> None:
        self.pattern.reset()
        self._blocked_until = time.monotonic() + cooldown
        self.paused = False

    def _audio_callback(
        self, indata: Any, _frames: int, _time_info: Any, _status: Any
    ) -> None:
        if self.paused or time.monotonic() < self._blocked_until:
            return
        peak = int(abs(indata).max())
        if self.pattern.feed(peak, time.monotonic()):
            self.paused = True
            self.on_double_clap()
