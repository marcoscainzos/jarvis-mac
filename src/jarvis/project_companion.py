from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
import json
from pathlib import Path
import re
import threading
from typing import Callable

from jarvis.screen_vision import ScreenVision


@dataclass(frozen=True)
class ProjectSession:
    active: bool
    project: str
    application: str
    started_at: str
    observations: int
    windows: tuple[str, ...]
    issues: tuple[str, ...]


class ProjectCompanion:
    """Observa bajo petición una sola aplicación y registra contexto local verificable."""

    def __init__(
        self,
        vision: ScreenVision,
        storage_path: Path,
        on_update: Callable[[ProjectSession, str], None] | None = None,
        interval: float = 12.0,
    ) -> None:
        self.vision = vision
        self.storage_path = storage_path
        self.on_update = on_update
        self.interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._session = ProjectSession(False, "", "", "", 0, (), ())
        self._load()

    def start(self, project_name: str = "") -> ProjectSession | None:
        application, title = self.vision.active_window_info()
        if not application:
            return None
        project = project_name.strip()[:120] or title.strip()[:120] or application
        with self._lock:
            if self._session.active:
                return self._session
            self._stop.clear()
            self._session = ProjectSession(
                True, project, application, datetime.now().isoformat(timespec="seconds"), 0,
                (title,) if title else (), (),
            )
            session = self._session
        self._save(session)
        threading.Thread(target=self._watch, daemon=True).start()
        return session

    def start_context(self) -> ProjectSession:
        """Inicia el contexto cotidiano siguiendo aplicaciones no sensibles."""
        application, title = self.vision.active_window_info()
        with self._lock:
            if self._session.active:
                return self._session
            self._stop.clear()
            self._session = ProjectSession(
                True, "Contexto de trabajo", "*", datetime.now().isoformat(timespec="seconds"),
                0, (f"{application}: {title}" if title else application,) if application else (), (),
            )
            session = self._session
        self._save(session)
        threading.Thread(target=self._watch, daemon=True).start()
        return session

    def stop(self) -> ProjectSession | None:
        with self._lock:
            if not self._session.active:
                return None
            self._stop.set()
            self._session = ProjectSession(**{**asdict(self._session), "active": False})
            session = self._session
        self._save(session)
        self._notify(session, "stopped")
        return session

    def status(self) -> ProjectSession:
        with self._lock:
            return self._session

    def _watch(self) -> None:
        while not self._stop.wait(self.interval):
            application, title = self.vision.active_window_info()
            with self._lock:
                expected = self._session.application
                active = self._session.active
            if not active or (expected != "*" and application != expected):
                continue
            if self._is_sensitive(application, title):
                continue
            _path, text = self.vision.read_active_window()
            if not text:
                continue
            issue = self._detect_issue(text)
            with self._lock:
                windows = list(self._session.windows)
                window_label = f"{application}: {title}" if title else application
                if window_label and window_label not in windows:
                    windows.append(window_label[:180])
                issues = list(self._session.issues)
                is_new_issue = bool(issue and issue not in issues)
                if is_new_issue:
                    issues.append(issue)
                self._session = ProjectSession(
                    True, self._session.project, self._session.application,
                    self._session.started_at, self._session.observations + 1,
                    tuple(windows[-12:]), tuple(issues[-12:]),
                )
                session = self._session
            self._save(session)
            self._notify(session, "issue" if is_new_issue else "progress")

    @staticmethod
    def _detect_issue(text: str) -> str:
        cues = re.compile(
            r"\b(error|exception|traceback|failed|failure|warning|no se pudo|"
            r"no se encuentra|module not found|modulenotfounderror|permission denied)\b",
            flags=re.IGNORECASE,
        )
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return next((line[:280] for line in lines if cues.search(line)), "")

    @staticmethod
    def _is_sensitive(application: str, title: str) -> bool:
        value = f"{application} {title}".casefold()
        blocked = (
            "password", "contraseña", "contrasena", "1password", "bitwarden",
            "keychain", "llavero", "banco", "banking", "wallet", "cartera",
            "private browsing", "navegación privada", "navegacion privada", "incognito",
        )
        return any(cue in value for cue in blocked)

    def _notify(self, session: ProjectSession, event: str) -> None:
        if self.on_update is not None:
            self.on_update(session, event)

    def _save(self, session: ProjectSession) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(
                json.dumps(asdict(session), ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError:
            pass

    def _load(self) -> None:
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            data["windows"] = tuple(data.get("windows", ()))
            data["issues"] = tuple(data.get("issues", ()))
            data["active"] = False
            self._session = ProjectSession(**data)
        except (OSError, ValueError, TypeError):
            pass
