from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory import SQLiteMemory


def test_project_memory_persists_structured_context() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "memory.db"
        memory = SQLiteMemory(path)
        memory.set_active_project("Jarvis")
        memory.remember_project("decision", "usar inteligencia local")
        memory.remember_project("pending", "mejorar la activación por voz")

        reopened = SQLiteMemory(path)
        context = reopened.project_context()
        assert reopened.active_project() == "Jarvis"
        assert "usar inteligencia local" in context
        assert "mejorar la activación por voz" in context


def test_project_memory_avoids_exact_duplicates() -> None:
    with TemporaryDirectory() as directory:
        memory = SQLiteMemory(Path(directory) / "memory.db")
        memory.set_active_project("Jarvis")
        memory.remember_project("note", "prueba")
        memory.remember_project("note", "prueba")
        assert memory.project_context().count("Nota: prueba") == 1
