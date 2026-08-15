from __future__ import annotations

import subprocess
import shutil
from datetime import datetime
from pathlib import Path
import re
import ssl
from urllib.parse import quote_plus
from urllib.request import Request, urlopen

import certifi
from jarvis.screen_vision import ScreenVision


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

    def __init__(self) -> None:
        self._screen_vision = ScreenVision()

    def read_active_window(self) -> tuple[Path | None, str]:
        return self._screen_vision.read_active_window()

    def capture_active_window(self) -> Path | None:
        return self._screen_vision.capture_active_window()

    def click_visible_text(self, text: str) -> bool:
        return self._screen_vision.click_visible_text(text)

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

    def open_path(self, path: Path) -> bool:
        if not self._is_managed_path(path) or not path.exists():
            return False
        return subprocess.run(
            ["open", str(path)], check=False, capture_output=True
        ).returncode == 0

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

    def create_text_file(self, name: str, content: str, location: str) -> Path | None:
        root = self._safe_root(location)
        safe_name = Path(name.strip()).name[:120]
        if root is None or not safe_name or safe_name in {".", ".."}:
            return None
        path = root / safe_name
        if path.exists():
            path = root / f"{path.stem} - nuevo{path.suffix}"
        try:
            path.write_text(content, encoding="utf-8")
        except OSError:
            return None
        return path

    def move_file(self, query: str, source: str, destination: str) -> Path | None:
        path = self.find_file(query, source)
        destination_root = self._safe_root(destination)
        if path is None or destination_root is None:
            return None
        target = destination_root / path.name
        if target.exists():
            return None
        try:
            return Path(shutil.move(str(path), str(target)))
        except OSError:
            return None

    def rename_file(self, query: str, location: str, new_name: str) -> Path | None:
        path = self.find_file(query, location)
        safe_name = Path(new_name.strip()).name[:150]
        if path is None or not safe_name or safe_name in {".", ".."}:
            return None
        target = path.with_name(safe_name)
        if target.exists():
            return None
        try:
            return path.rename(target)
        except OSError:
            return None

    def trash_file(self, query: str, location: str) -> bool:
        path = self.find_file(query, location)
        if path is None:
            return False
        script = """
on run argv
    tell application "Finder" to delete POSIX file (item 1 of argv)
end run
"""
        return self._osascript(script, str(path))

    @staticmethod
    def _safe_root(location: str) -> Path | None:
        roots = {
            "desktop": Path.home() / "Desktop",
            "downloads": Path.home() / "Downloads",
            "documents": Path.home() / "Documents",
        }
        return roots.get(location)

    @classmethod
    def _is_managed_path(cls, path: Path) -> bool:
        try:
            resolved = path.resolve()
            return any(
                resolved == root.resolve() or root.resolve() in resolved.parents
                for root in filter(None, (cls._safe_root(name) for name in ("desktop", "downloads", "documents")))
            )
        except OSError:
            return False

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

    def show_research_source(self, url: str, first: bool = False) -> bool:
        """Muestra las fuentes en una ventana de Safari situada a la derecha."""
        if not url.startswith(("http://", "https://")):
            return False
        if first:
            script = """
on run argv
    tell application "System Events"
        set previousProcess to first application process whose frontmost is true
    end tell
    tell application "Finder" to set screenBounds to bounds of window of desktop
    set screenWidth to item 3 of screenBounds
    set screenHeight to item 4 of screenBounds
    tell application "Safari"
        activate
        make new document with properties {URL:item 1 of argv}
    end tell
    delay 0.4
    tell application "System Events"
        tell process "Safari"
            set position of front window to {screenWidth / 2, 25}
            set size of front window to {screenWidth / 2, screenHeight - 25}
        end tell
        set frontmost of previousProcess to true
    end tell
end run
"""
        else:
            script = """
on run argv
    tell application "Safari"
        if (count of windows) is 0 then
            make new document with properties {URL:item 1 of argv}
        else
            tell front window
                set newTab to make new tab with properties {URL:item 1 of argv}
                set current tab to newTab
            end tell
        end if
    end tell
end run
"""
        if self._osascript(script, url):
            return True
        # Sin permiso de Accesibilidad no puede mover la ventana, pero sí mostrar la fuente.
        return subprocess.run(
            ["open", "-a", "Safari", url],
            check=False,
            capture_output=True,
            text=True,
        ).returncode == 0

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
