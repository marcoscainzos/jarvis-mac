from __future__ import annotations

from collections.abc import Sequence
from typing import Any


def select_input_device(
    devices: Sequence[dict[str, Any]], default_index: int | None = None
) -> int | None:
    """Elige un micrófono real y evita rutas virtuales de captura."""
    blocked = (
        "blackhole", "soundflower", "loopback", "aggregate", "multi-output",
        "zoom", "teams", "screen capture", "captura de pantalla",
    )
    preferred = ("macbook", "microphone", "micrófono", "mic", "airpods")
    candidates: list[tuple[int, int]] = []
    for index, device in enumerate(devices):
        if int(device.get("max_input_channels", 0)) < 1:
            continue
        name = str(device.get("name", "")).casefold()
        if any(cue in name for cue in blocked):
            continue
        score = 100 if default_index == index else 0
        score += 25 if any(cue in name for cue in preferred) else 0
        score += min(int(device.get("max_input_channels", 1)), 4)
        candidates.append((score, index))
    return max(candidates, default=(0, None))[1]
