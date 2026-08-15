from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from jarvis.research import ResearchResult
from jarvis.task_engine import TaskEngine


class FakeResearcher:
    def __init__(self) -> None:
        self.done = threading.Event()

    def start(self, _query: str) -> bool:
        self.done.set()
        return True

    def status(self):
        return ("done", "terminada") if self.done.is_set() else ("running", "buscando")

    def result(self):
        return ResearchResult("tema", "Comparación final", (("Fuente", "https://example.com"),))


class FakeTools:
    def __init__(self, root: Path) -> None:
        self.root = root

    def create_text_file(self, name: str, content: str, _location: str):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path


def test_task_engine_creates_and_verifies_report() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        engine = TaskEngine(FakeResearcher(), FakeTools(root), root / "task.json")
        assert engine.start_research_report("tema")
        for _ in range(100):
            if engine.status().state == "done":
                break
            threading.Event().wait(0.01)
        snapshot = engine.status()
        assert snapshot.state == "done"
        assert Path(snapshot.output).exists()
        assert "Comparación final" in Path(snapshot.output).read_text(encoding="utf-8")
