from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import threading
import time
from typing import Callable

from jarvis.computer_tools import ComputerTools
from jarvis.research import BackgroundResearcher, ResearchResult


@dataclass(frozen=True)
class TaskSnapshot:
    state: str
    goal: str
    step: str
    output: str = ""
    error: str = ""


class TaskEngine:
    """Ejecuta objetivos largos con estado verificable y cancelación segura."""

    def __init__(
        self,
        researcher: BackgroundResearcher,
        tools: ComputerTools,
        storage_path: Path,
        on_update: Callable[[TaskSnapshot], None] | None = None,
    ) -> None:
        self.researcher = researcher
        self.tools = tools
        self.storage_path = storage_path
        self.on_update = on_update
        self._lock = threading.Lock()
        self._cancel = threading.Event()
        self._snapshot = TaskSnapshot("idle", "", "Sin tareas")
        self._load()

    def start_research_report(
        self, query: str, location: str = "desktop"
    ) -> bool:
        clean_query = query.strip()[:500]
        with self._lock:
            if self._snapshot.state == "running" or not clean_query:
                return False
            self._cancel.clear()
        self._set(TaskSnapshot("running", clean_query, "Buscando fuentes"))
        if not self.researcher.start(clean_query):
            self._set(TaskSnapshot("error", clean_query, "No iniciada", error="Ya hay una investigación en curso"))
            return False
        threading.Thread(
            target=self._finish_research_report,
            args=(clean_query, location),
            daemon=True,
        ).start()
        return True

    def status(self) -> TaskSnapshot:
        with self._lock:
            snapshot = self._snapshot
        if snapshot.state == "running":
            research_state, progress = self.researcher.status()
            if research_state == "running" and progress:
                return TaskSnapshot("running", snapshot.goal, progress)
        return snapshot

    def cancel(self) -> bool:
        with self._lock:
            if self._snapshot.state != "running":
                return False
            goal = self._snapshot.goal
        self._cancel.set()
        self._set(TaskSnapshot("cancelled", goal, "Tarea cancelada"))
        return True

    def _finish_research_report(self, query: str, location: str) -> None:
        while not self._cancel.is_set():
            state, detail = self.researcher.status()
            if state == "done":
                break
            if state == "error":
                self._set(TaskSnapshot("error", query, "Investigación detenida", error=detail))
                return
            time.sleep(0.25)
        if self._cancel.is_set():
            return
        result = self.researcher.result()
        if result is None:
            self._set(TaskSnapshot("error", query, "Sin resultados", error="No se obtuvo un resultado verificable"))
            return
        self._set(TaskSnapshot("running", query, "Creando y verificando el informe"))
        filename = self._filename(query)
        path = self.tools.create_text_file(filename, self._report(result), location)
        if path is None or not path.exists() or path.stat().st_size < 20:
            self._set(TaskSnapshot("error", query, "No se guardó el informe", error="No pude verificar el archivo de salida"))
            return
        self._set(TaskSnapshot("done", query, "Tarea terminada", output=str(path)))

    def _set(self, snapshot: TaskSnapshot) -> None:
        with self._lock:
            self._snapshot = snapshot
        self._save(snapshot)
        if self.on_update is not None:
            self.on_update(snapshot)

    def _save(self, snapshot: TaskSnapshot) -> None:
        try:
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self.storage_path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2), encoding="utf-8")
        except OSError:
            pass

    def _load(self) -> None:
        try:
            data = json.loads(self.storage_path.read_text(encoding="utf-8"))
            snapshot = TaskSnapshot(**data)
            if snapshot.state == "running":
                snapshot = TaskSnapshot("error", snapshot.goal, "Tarea interrumpida", error="Jarvis se cerró antes de terminar")
            self._snapshot = snapshot
        except (OSError, ValueError, TypeError):
            pass

    @staticmethod
    def _filename(query: str) -> str:
        safe = re.sub(r"[^a-zA-Z0-9áéíóúüñÁÉÍÓÚÜÑ -]", "", query).strip()
        return f"Informe - {safe[:70] or 'investigación'}.md"

    @staticmethod
    def _report(result: ResearchResult) -> str:
        sources = "\n".join(f"- [{title}]({url})" for title, url in result.sources)
        return f"# Informe: {result.query}\n\n{result.summary}\n\n## Fuentes consultadas\n\n{sources}\n"
