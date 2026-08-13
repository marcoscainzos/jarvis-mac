from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class Reply:
    message: str
    should_exit: bool = False


class Assistant:
    """Interpreta las primeras órdenes sin enviar datos fuera del Mac."""

    def __init__(self, open_app: Callable[[str], bool]) -> None:
        self._open_app = open_app

    def handle(self, command: str) -> Reply:
        normalized = " ".join(command.lower().strip().split())

        if not normalized:
            return Reply("No he oído ninguna orden.")
        if normalized in {"salir", "adiós", "adios", "terminar"}:
            return Reply("Hasta pronto.", should_exit=True)
        if normalized in {"hola", "hola jarvis"}:
            return Reply("Hola. Estoy listo para ayudarte.")
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
            "Todavía no conozco esa orden. Prueba con “hola”, “qué hora es” "
            "o “abre Calculadora”."
        )

