from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.memory import SQLiteMemory
from jarvis.assistant import Assistant


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


def test_can_complete_move_and_forget_memories() -> None:
    with TemporaryDirectory() as directory:
        memory = SQLiteMemory(Path(directory) / "memory.db")
        memory.set_active_project("Iris")
        memory.remember_project("pending", "probar la voz")
        assert memory.complete_latest_pending()
        assert "Completado: probar la voz" in memory.project_context()
        assert memory.move_latest_project_memory("Aplicación")
        assert "probar la voz" in memory.project_context("Aplicación")
        memory.set_active_project("Aplicación")
        assert memory.forget_latest_project_memory()
        assert "probar la voz" not in memory.project_context()


def test_automatic_memory_asks_permission_and_respects_private_mode() -> None:
    with TemporaryDirectory() as directory:
        memory = SQLiteMemory(Path(directory) / "memory.db")
        memory.set_active_project("Iris")
        assistant = Assistant(lambda _name: False, memory=memory)
        prompt = assistant.handle("Tenemos que mejorar la activación")
        assert "quieres que lo recuerde" in prompt.message.casefold()
        assistant.handle("sí")
        assert "mejorar la activacion" in memory.project_context()

        assistant.handle("no guardes esta conversación")
        assistant.handle("Recuerda que este dato es temporal")
        assert "dato es temporal" not in memory.project_context()
