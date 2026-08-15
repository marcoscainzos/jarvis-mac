from pathlib import Path
from tempfile import TemporaryDirectory
import threading

from jarvis.research import BackgroundResearcher


def test_research_runs_in_background_and_persists_result() -> None:
    completed = threading.Event()
    summarizing = threading.Event()
    release = threading.Event()
    with TemporaryDirectory() as directory:
        storage = Path(directory) / "research.json"
        researcher = BackgroundResearcher(
            lambda query, sources: (
                summarizing.set(),
                release.wait(2.0),
                f"Resumen de {query} con {len(sources)} fuentes.",
            )[-1],
            on_complete=lambda _result: completed.set(),
            storage_path=storage,
        )
        researcher._search = lambda _query: [
            ("Fuente uno", "https://example.com/uno", "Descripción uno"),
            ("Fuente dos", "https://example.com/dos", "Descripción dos"),
        ]
        researcher._fetch_text = lambda url: f"Contenido de {url}"

        assert researcher.start("una pregunta") is True
        assert summarizing.wait(2.0)
        assert researcher.start("otra pregunta") is False
        release.set()
        assert completed.wait(2.0)
        result = researcher.result()

        assert result is not None
        assert "2 fuentes" in result.summary
        assert len(result.sources) == 2
        assert storage.exists()

        restored = BackgroundResearcher(lambda _query, _sources: "", storage_path=storage)
        assert restored.result() == result
