from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from jarvis.project_companion import ProjectCompanion


class FakeVision:
    def active_window_info(self):
        return "Visual Studio Code", "jarvis-mac — assistant.py"

    def read_active_window(self):
        return Path("/tmp/fake.png"), "Traceback\nModuleNotFoundError: No module named jarvis"


def test_project_companion_observes_only_after_explicit_start() -> None:
    with TemporaryDirectory() as directory:
        updates = threading.Event()
        companion = ProjectCompanion(
            FakeVision(), Path(directory) / "session.json",
            on_update=lambda _session, event: updates.set() if event == "issue" else None,
            interval=0.01,
        )
        assert companion.status().active is False
        session = companion.start()
        assert session is not None
        assert session.application == "Visual Studio Code"
        assert updates.wait(1.0)
        stopped = companion.stop()
        assert stopped is not None
        assert stopped.active is False
        assert stopped.observations >= 1
        assert any("Traceback" in issue or "ModuleNotFoundError" in issue for issue in stopped.issues)


def test_project_companion_does_not_watch_other_applications() -> None:
    class ChangingVision(FakeVision):
        def active_window_info(self):
            return "Safari", "Privado"

    with TemporaryDirectory() as directory:
        companion = ProjectCompanion(ChangingVision(), Path(directory) / "session.json", interval=0.01)
        companion.start("Proyecto")
        # Cambiamos la aplicación permitida después de iniciar para simular salir del proyecto.
        companion.vision.active_window_info = lambda: ("Mail", "Correo privado")
        threading.Event().wait(0.05)
        assert companion.stop().observations == 0


def test_always_context_follows_safe_applications_and_skips_passwords() -> None:
    with TemporaryDirectory() as directory:
        vision = FakeVision()
        companion = ProjectCompanion(vision, Path(directory) / "session.json", interval=0.01)
        session = companion.start_context()
        assert session.application == "*"
        threading.Event().wait(0.04)
        assert companion.status().observations >= 1
        assert companion._is_sensitive("Safari", "Banco - contraseña") is True
