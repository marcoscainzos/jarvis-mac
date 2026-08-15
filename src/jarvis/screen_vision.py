from __future__ import annotations

from datetime import datetime
from pathlib import Path
import subprocess
from typing import Any


class ScreenVision:
    """Captura y lee texto visible usando exclusivamente APIs locales de macOS."""

    def capture_active_window(self) -> Path | None:
        window_id = self._front_window_id()
        if window_id is None:
            return None
        folder = Path.home() / "Pictures" / "Jarvis"
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
        return path, self.read_text(path)

    @staticmethod
    def _front_window_id() -> int | None:
        import Quartz

        options = (
            Quartz.kCGWindowListOptionOnScreenOnly
            | Quartz.kCGWindowListExcludeDesktopElements
        )
        windows: list[dict[str, Any]] = Quartz.CGWindowListCopyWindowInfo(
            options, Quartz.kCGNullWindowID
        )
        ignored = {"Jarvis", "Dock", "Window Server", "Control Center"}
        for window in windows:
            if window.get("kCGWindowLayer") != 0:
                continue
            if window.get("kCGWindowOwnerName") in ignored:
                continue
            bounds = window.get("kCGWindowBounds", {})
            if bounds.get("Width", 0) < 150 or bounds.get("Height", 0) < 100:
                continue
            return int(window["kCGWindowNumber"])
        return None

    @staticmethod
    def read_text(path: Path) -> str:
        try:
            import Vision
            from Foundation import NSURL
        except ImportError:
            return ""

        request = Vision.VNRecognizeTextRequest.alloc().init()
        request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
        request.setRecognitionLanguages_(["es-ES", "en-US"])
        request.setUsesLanguageCorrection_(True)
        handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
            NSURL.fileURLWithPath_(str(path)), {}
        )
        success, _error = handler.performRequests_error_([request], None)
        if not success:
            return ""
        lines: list[str] = []
        for observation in request.results() or []:
            candidates = observation.topCandidates_(1)
            if candidates:
                lines.append(str(candidates[0].string()))
        return "\n".join(lines)[:12_000]
