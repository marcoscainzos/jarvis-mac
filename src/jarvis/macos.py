from __future__ import annotations

import subprocess
from datetime import datetime


ALLOWED_APPS = {
    "calculadora": "Calculator",
    "calculator": "Calculator",
    "calendario": "Calendar",
    "calendar": "Calendar",
    "notas": "Notes",
    "notes": "Notes",
    "musica": "Music",
    "música": "Music",
    "recordatorios": "Reminders",
    "spotify": "Spotify",
    "safari": "Safari",
    "terminal": "Terminal",
}


def open_application(requested_name: str) -> bool:
    """Abre únicamente aplicaciones incluidas en la lista segura."""
    app_name = ALLOWED_APPS.get(requested_name.lower().strip())
    if app_name is None:
        return False

    result = subprocess.run(
        ["open", "-a", app_name],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


class MacOSComputerTools:
    """Acciones locales concretas; no ejecuta comandos arbitrarios del modelo."""

    def control_music(self, action: str) -> bool:
        commands = {
            "play_pause": 'tell application "Music" to playpause',
            "next": 'tell application "Music" to next track',
            "previous": 'tell application "Music" to previous track',
        }
        script = commands.get(action)
        return script is not None and self._osascript(script)

    def set_volume(self, level: int) -> bool:
        safe_level = max(0, min(100, level))
        return self._osascript(f"set volume output volume {safe_level}")

    def create_reminder(self, title: str, due: datetime) -> bool:
        script = """
on run argv
    set dueDate to current date
    set year of dueDate to (item 2 of argv as integer)
    set month of dueDate to (item 3 of argv as integer)
    set day of dueDate to (item 4 of argv as integer)
    set hours of dueDate to (item 5 of argv as integer)
    set minutes of dueDate to (item 6 of argv as integer)
    set seconds of dueDate to 0
    tell application "Reminders"
        set targetList to first list
        tell targetList to make new reminder with properties {name:item 1 of argv, due date:dueDate}
    end tell
end run
"""
        return self._osascript(script, title, *self._date_parts(due))

    def create_calendar_event(
        self, title: str, start: datetime, end: datetime
    ) -> bool:
        script = """
on run argv
    set startDate to current date
    set year of startDate to (item 2 of argv as integer)
    set month of startDate to (item 3 of argv as integer)
    set day of startDate to (item 4 of argv as integer)
    set hours of startDate to (item 5 of argv as integer)
    set minutes of startDate to (item 6 of argv as integer)
    set seconds of startDate to 0
    set endDate to startDate + (item 7 of argv as integer)
    tell application "Calendar"
        set targetCalendar to first calendar whose writable is true
        tell targetCalendar to make new event with properties {summary:item 1 of argv, start date:startDate, end date:endDate}
    end tell
end run
"""
        duration = max(60, int((end - start).total_seconds()))
        return self._osascript(script, title, *self._date_parts(start), duration)

    @staticmethod
    def _date_parts(value: datetime) -> tuple[int, int, int, int, int]:
        return value.year, value.month, value.day, value.hour, value.minute

    @staticmethod
    def _osascript(script: str, *arguments: object) -> bool:
        result = subprocess.run(
            ["osascript", "-e", script, *[str(value) for value in arguments]],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0
