from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any
import unicodedata


class ScreenVision:
    """Captura y lee texto visible usando exclusivamente APIs locales de macOS."""

    def capture_active_window(self) -> Path | None:
        window_id = self._front_window_id()
        if window_id is None:
            return None
        folder = Path.home() / "Pictures" / "Iris"
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"ventana-{datetime.now():%Y%m%d-%H%M%S}.png"
        result = subprocess.run(
            ["/usr/sbin/screencapture", "-x", "-l", str(window_id), str(path)],
            check=False,
            capture_output=True,
        )
        return path if result.returncode == 0 and path.exists() else None

    def read_active_window(self) -> tuple[Path | None, str]:
        path = self.capture_active_window()
        if path is None:
            return None, ""
        text = self.read_text(path)
        path.unlink(missing_ok=True)
        return path, text

    def click_visible_text(self, requested_text: str) -> bool:
        """Pulsa texto visible solo cuando el usuario nombra el elemento explícitamente."""
        window = self._front_window()
        if window is None:
            return False
        path = self.capture_active_window()
        if path is None:
            return False
        try:
            observations = self._recognize(path)
            needle = self._normalize(requested_text)
            matches = [
                item for item in observations
                if needle in self._normalize(item[0])
                or self._normalize(item[0]) in needle
            ]
            if not matches:
                return False
            _label, box = min(matches, key=lambda item: len(item[0]))
            bounds = window["kCGWindowBounds"]
            x = float(bounds["X"]) + (box.origin.x + box.size.width / 2) * float(bounds["Width"])
            y = float(bounds["Y"]) + (1 - box.origin.y - box.size.height / 2) * float(bounds["Height"])
            import Quartz
            down = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseDown, (x, y), Quartz.kCGMouseButtonLeft)
            up = Quartz.CGEventCreateMouseEvent(None, Quartz.kCGEventLeftMouseUp, (x, y), Quartz.kCGMouseButtonLeft)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, down)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, up)
            return True
        finally:
            path.unlink(missing_ok=True)

    @staticmethod
    def _front_window_id() -> int | None:
        window = ScreenVision._front_window()
        return int(window["kCGWindowNumber"]) if window is not None else None

    @staticmethod
    def _front_window() -> dict[str, Any] | None:
        import Quartz

        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        windows: list[dict[str, Any]] = Quartz.CGWindowListCopyWindowInfo(
            options, Quartz.kCGNullWindowID
        )
        ignored = {"Iris", "Jarvis", "Dock", "Window Server", "Control Center"}
        for window in windows:
            if window.get("kCGWindowLayer") != 0:
                continue
            if window.get("kCGWindowOwnerName") in ignored:
                continue
            bounds = window.get("kCGWindowBounds", {})
            if bounds.get("Width", 0) < 150 or bounds.get("Height", 0) < 100:
                continue
            return window
        return None

    @staticmethod
    def read_text(path: Path) -> str:
        return "\n".join(text for text, _box in ScreenVision._recognize(path))[:12_000]

    @staticmethod
    def _recognize(path: Path) -> list[tuple[str, Any]]:
        try:
            import Vision
            from Foundation import NSURL
        except ImportError:
            return []

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["es-ES", "en-US"])
        request.setUsesLanguageCorrection_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
            NSURL.fileURLWithPath_(str(path)), {}
        )
        success, _error = handler.performRequests_error_([request], None)
        if not success:
            return []
        lines: list[tuple[str, Any]] = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                lines.append((str(candidates[0].string()), observation.boundingBox()))
        return lines

    @staticmethod
    def _normalize(text: str) -> str:
        value = unicodedata.normalize("NFD", text.casefold())
        return "".join(character for character in value if unicodedata.category(character) != "Mn").strip()
    def active_window_info(self) -> tuple[str, str]:
        window = self._front_window()
        if window is None:
            return "", ""
        return (
            str(window.get("kCGWindowOwnerName", "")),
            str(window.get("kCGWindowName", "")),
        )
