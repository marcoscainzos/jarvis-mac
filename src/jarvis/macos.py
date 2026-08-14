from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
import re
import ssl
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import certifi


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
    """Abre una aplicación instalada sin ejecutar comandos del usuario."""
    requested = requested_name.strip()[:100]
    if not requested or any(character in requested for character in ";|&`$\n"):
        return False
    app_name = ALLOWED_APPS.get(requested.lower(), requested)

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

    def play_music(self, query: str) -> bool:
        """Abre directamente el primer vídeo que devuelve YouTube."""
        safe_query = query.strip()[:200]
        if not safe_query:
            return self.control_music("play_pause")
        url = f"https://www.youtube.com/results?search_query={quote_plus(safe_query)}"
        try:
            request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
            tls_context = ssl.create_default_context(cafile=certifi.where())
            with urlopen(request, timeout=8, context=tls_context) as response:
                page = response.read(2_000_000).decode("utf-8", errors="ignore")
            video_ids = re.findall(r'"videoId":"([A-Za-z0-9_-]{11})"', page)
            if video_ids:
                url = f"https://www.youtube.com/watch?v={video_ids[0]}&autoplay=1"
        except (OSError, TimeoutError):
            pass
        result = subprocess.run(
            [
                "open",
                "-a",
                "Safari",
                url,
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

    def list_files(self, location: str) -> list[str]:
        root = self._safe_root(location)
        if root is None:
            return []
        try:
            entries = sorted(root.iterdir(), key=lambda path: path.stat().st_mtime, reverse=True)
        except OSError:
            return []
        return [entry.name for entry in entries[:8] if not entry.name.startswith(".")]

    def find_file(self, query: str, location: str) -> Path | None:
        root = self._safe_root(location)
        needle = query.casefold().strip()
        if root is None or not needle:
            return None
        try:
            candidates = (
                path for path in root.rglob("*")
                if not any(part.startswith(".") for part in path.relative_to(root).parts)
                and needle in path.name.casefold()
            )
            return next(candidates, None)
        except (OSError, PermissionError):
            return None

    def open_file(self, query: str, location: str) -> Path | None:
        path = self.find_file(query, location)
        if path is None:
            return None
        result = subprocess.run(["open", str(path)], check=False, capture_output=True)
        return path if result.returncode == 0 else None

    def create_folder(self, name: str, location: str) -> Path | None:
        root = self._safe_root(location)
        safe_name = Path(name.strip()).name[:100]
        if root is None or not safe_name or safe_name in {".", ".."}:
            return None
        path = root / safe_name
        try:
            path.mkdir(exist_ok=False)
        except OSError:
            return None
        return path

    @staticmethod
    def _safe_root(location: str) -> Path | None:
        roots = {
            "desktop": Path.home() / "Desktop",
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
        }
        return roots.get(location)

    def search_web(self, query: str) -> bool:
        safe_query = query.strip()[:500]
        if not safe_query:
            return False
        result = subprocess.run(
            ["open", f"https://www.google.com/search?q={quote_plus(safe_query)}"],
            check=False,
            capture_output=True,
            text=True,
        )
        return result.returncode == 0

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
