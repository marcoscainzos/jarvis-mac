from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Protocol


class Memory(Protocol):
    def get(self, key: str) -> str | None: ...

    def set(self, key: str, value: str) -> None: ...

    def forget(self, key: str) -> None: ...


class SQLiteMemory:
    """Memoria clave-valor local, pequeña y portable."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS memory "
                "(key TEXT PRIMARY KEY, value TEXT NOT NULL)"
            )
            connection.execute(
                "CREATE TABLE IF NOT EXISTS project_memory ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, project TEXT NOT NULL, "
                "category TEXT NOT NULL, content TEXT NOT NULL, "
                "created_at TEXT NOT NULL)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def get(self, key: str) -> str | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT value FROM memory WHERE key = ?", (key,)
            ).fetchone()
        return row[0] if row else None

    def set(self, key: str, value: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO memory(key, value) VALUES (?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, value),
            )

    def forget(self, key: str) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM memory WHERE key = ?", (key,))

    def set_active_project(self, project: str) -> None:
        project = " ".join(project.split())[:120]
        self.set("active_project", project)
        self.set("active_project_date", datetime.now().isoformat(timespec="seconds"))

    def active_project(self) -> str | None:
        return self.get("active_project")

    def remember_project(self, category: str, content: str, project: str = "") -> None:
        selected = project.strip() or self.active_project() or "General"
        clean = " ".join(content.split())[:600]
        if not clean:
            return
        with self._connect() as connection:
            duplicate = connection.execute(
                "SELECT 1 FROM project_memory WHERE project = ? AND category = ? "
                "AND content = ? LIMIT 1", (selected, category, clean)
            ).fetchone()
            if duplicate is None:
                connection.execute(
                    "INSERT INTO project_memory(project, category, content, created_at) "
                    "VALUES (?, ?, ?, ?)",
                    (selected, category, clean, datetime.now().isoformat(timespec="seconds")),
                )

    def project_context(self, project: str = "", limit: int = 12) -> str:
        selected = project.strip() or self.active_project() or ""
        if not selected:
            return ""
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT category, content, created_at FROM project_memory "
                "WHERE project = ? ORDER BY id DESC LIMIT ?", (selected, limit)
            ).fetchall()
        if not rows:
            return f"Proyecto activo: {selected}. Todavía no hay detalles guardados."
        labels = {"decision": "Decisión", "preference": "Preferencia", "pending": "Pendiente", "completed": "Completado", "note": "Nota"}
        details = "\n".join(
            f"- {labels.get(category, category)}: {content} ({created_at[:10]})"
            for category, content, created_at in reversed(rows)
        )
        return f"Proyecto activo: {selected}\n{details}"

    def forget_latest_project_memory(self, category: str = "") -> bool:
        selected = self.active_project() or "General"
        with self._connect() as connection:
            if category:
                row = connection.execute(
                    "SELECT id FROM project_memory WHERE project = ? AND category = ? "
                    "ORDER BY id DESC LIMIT 1", (selected, category)
                ).fetchone()
            else:
                row = connection.execute(
                    "SELECT id FROM project_memory WHERE project = ? ORDER BY id DESC LIMIT 1",
                    (selected,),
                ).fetchone()
            if row is None:
                return False
            connection.execute("DELETE FROM project_memory WHERE id = ?", (row[0],))
        return True

    def move_latest_project_memory(self, project: str) -> bool:
        selected = self.active_project() or "General"
        clean_project = " ".join(project.split())[:120]
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM project_memory WHERE project = ? ORDER BY id DESC LIMIT 1",
                (selected,),
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "UPDATE project_memory SET project = ? WHERE id = ?", (clean_project, row[0])
            )
        return True

    def complete_latest_pending(self) -> bool:
        selected = self.active_project() or "General"
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id FROM project_memory WHERE project = ? AND category = 'pending' "
                "ORDER BY id DESC LIMIT 1", (selected,)
            ).fetchone()
            if row is None:
                return False
            connection.execute(
                "UPDATE project_memory SET category = 'completed' WHERE id = ?", (row[0],)
            )
        return True


class VolatileMemory:
    """Memoria efímera para pruebas y dispositivos sin almacenamiento."""

    def __init__(self) -> None:
        self.values: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.values.get(key)

    def set(self, key: str, value: str) -> None:
        self.values[key] = value

    def forget(self, key: str) -> None:
        self.values.pop(key, None)
