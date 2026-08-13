from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from jarvis.memory import Memory, VolatileMemory


@dataclass(frozen=True)
class Reply:
    message: str
    should_exit: bool = False


class Assistant:
    """Interpreta las primeras órdenes sin enviar datos fuera del Mac."""

    def __init__(
        self, open_app: Callable[[str], bool], memory: Memory | None = None
    ) -> None:
        self._open_app = open_app
        self._memory = memory or VolatileMemory()

    def handle(self, command: str) -> Reply:
        normalized = " ".join(command.lower().strip().split())

        if not normalized:
            return Reply("No he oído ninguna orden.")
        if normalized in {"salir", "adiós", "adios", "terminar"}:
            return Reply("Hasta pronto.", should_exit=True)
        if normalized in {"hola", "hola jarvis"}:
            name = self._memory.get("user_name")
            greeting = f"Hola, {name}." if name else "Hola."
            return Reply(f"{greeting} Estoy listo para ayudarte.")
        if normalized in {"qué sabes de mí", "que sabes de mi"}:
            name = self._memory.get("user_name")
            if name:
                return Reply(f"Sé que te llamas {name}. No guardo nada más por ahora.")
            return Reply("Todavía no sé nada de ti.")
        if normalized in {"olvida mi nombre", "olvídate de mi nombre"}:
            self._memory.forget("user_name")
            return Reply("He olvidado tu nombre.")
        name = self._extract_name(command, normalized)
        if name:
            self._memory.set("user_name", name)
            return Reply(f"Encantado, {name}. Lo recordaré en este dispositivo.")
        if normalized in {"ayuda", "qué puedes hacer", "que puedes hacer"}:
            return Reply(
                "Puedo recordar tu nombre, decir la hora y abrir aplicaciones seguras. "
                "Por ejemplo: me llamo Marcos, qué sabes de mí o abre Notas."
            )
        if normalized in {"qué hora es", "que hora es", "hora"}:
            return Reply(f"Son las {datetime.now():%H:%M}.")
        if normalized.startswith("abre "):
            app_name = command.strip()[5:].strip()
            if not app_name:
                return Reply("Dime qué aplicación quieres abrir.")
            if self._open_app(app_name):
                return Reply(f"Abriendo {app_name}.")
            return Reply(
                f"No puedo abrir {app_name}. Por seguridad solo utilizo aplicaciones permitidas."
            )

        return Reply(
            "Todavía no conozco esa orden. Di “qué puedes hacer” para ver ejemplos."
        )

    @staticmethod
    def _extract_name(command: str, normalized: str) -> str | None:
        prefixes = ("me llamo ", "mi nombre es ")
        for prefix in prefixes:
            if normalized.startswith(prefix):
                name = command.strip()[len(prefix) :].strip(" .,!¿?¡")
                if name and len(name) <= 60:
                    return name
        return None
