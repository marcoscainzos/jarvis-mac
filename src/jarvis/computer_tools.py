from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ComputerTools(Protocol):
    def control_music(self, action: str) -> bool: ...

    def set_volume(self, level: int) -> bool: ...

    def create_reminder(self, title: str, due: datetime) -> bool: ...

    def create_calendar_event(
        self, title: str, start: datetime, end: datetime
    ) -> bool: ...
