from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Callable
import unicodedata

from jarvis.memory import Memory, VolatileMemory
from jarvis.local_ai import ConversationalAI
from jarvis.computer_tools import ComputerTools


@dataclass(frozen=True)
class Reply:
    message: str
    should_exit: bool = False


class Assistant:
    """Interpreta las primeras órdenes sin enviar datos fuera del Mac."""

    def __init__(
        self,
        open_app: Callable[[str], bool],
        memory: Memory | None = None,
        conversational_ai: ConversationalAI | None = None,
        computer_tools: ComputerTools | None = None,
    ) -> None:
        self._open_app = open_app
        self._memory = memory or VolatileMemory()
        self._conversational_ai = conversational_ai
        self._computer_tools = computer_tools

    def handle(self, command: str) -> Reply:
        normalized = self._normalize(command)

        if not normalized:
            return Reply("No he oído ninguna orden.")
        if normalized in {
            "salir",
            "adios",
            "terminar",
            "duerme",
            "duerme jarvis",
            "jarvis duerme",
        }:
            return Reply("Hasta pronto.", should_exit=True)
        if normalized in {"jarvis", "allervis", "alervis"}:
            return Reply("Sí, señor.")
        if normalized in {
            "hola",
            "hola jarvis",
            "hola allervis",
            "hola alervis",
        }:
            name = self._memory.get("user_name")
            if name:
                return Reply(f"Hola, {name}. Estoy listo para ayudarte.")
            if self._conversational_ai is None:
                return Reply("Hola. Estoy listo para ayudarte.")
        if normalized == "que sabes de mi":
            name = self._memory.get("user_name")
            if name:
                return Reply(f"Sé que te llamas {name}. No guardo nada más por ahora.")
            return Reply("Todavía no sé nada de ti.")
        if normalized in {"olvida mi nombre", "olvidate de mi nombre"}:
            self._memory.forget("user_name")
            return Reply("He olvidado tu nombre.")
        name = self._extract_name(command, normalized)
        if name:
            self._memory.set("user_name", name)
            return Reply(f"Encantado, {name}. Lo recordaré en este dispositivo.")
        if normalized in {"ayuda", "que puedes hacer"}:
            return Reply(
                "Puedo conversar contigo recordando el contexto, abrir aplicaciones, "
                "buscar en internet, controlar la música y el volumen, y crear "
                "recordatorios o eventos. Puedes pedírmelo con tus propias palabras."
            )
        if normalized in {"que hora es", "hora"}:
            return Reply(f"Son las {datetime.now():%H:%M}.")
        action_reply = self._handle_computer_action(command, normalized)
        if action_reply is not None:
            return action_reply
        if normalized.startswith("abre "):
            app_name = command.strip()[5:].strip()
            if not app_name:
                return Reply("Dime qué aplicación quieres abrir.")
            if self._open_app(app_name):
                return Reply(f"Abriendo {app_name}.")
            return Reply(
                f"No puedo abrir {app_name}. Por seguridad solo utilizo aplicaciones permitidas."
            )

        if self._conversational_ai is not None:
            try:
                return Reply(self._conversational_ai.reply(command))
            except RuntimeError as error:
                return Reply(str(error))
        return Reply("Todavía no conozco esa orden.")

    def _handle_computer_action(
        self, command: str, normalized: str
    ) -> Reply | None:
        if self._computer_tools is None:
            return None

        music_actions = {
            "pon musica": ("play_pause", "Reproduciendo música."),
            "reproduce musica": ("play_pause", "Reproduciendo música."),
            "pausa la musica": ("play_pause", "Música pausada."),
            "pausa musica": ("play_pause", "Música pausada."),
            "siguiente cancion": ("next", "Pasando a la siguiente canción."),
            "cancion siguiente": ("next", "Pasando a la siguiente canción."),
            "cancion anterior": ("previous", "Volviendo a la canción anterior."),
        }
        if normalized in music_actions:
            action, success = music_actions[normalized]
            if self._computer_tools.control_music(action):
                return Reply(success)
            return Reply("No he podido controlar Música.")

        requested_music = re.match(
            r"(?:pon|reproduce|toca|quiero escuchar)\s+(?:la cancion\s+|musica de\s+)?(.+)",
            normalized,
        )
        if requested_music and not normalized.startswith(("pon el volumen", "pon volumen")):
            query = requested_music.group(1).strip()
            if query not in {"musica", "algo de musica"}:
                if self._computer_tools.play_music(query):
                    return Reply(f"Reproduciendo {query}.")
                return Reply(f"No he encontrado {query} en tu biblioteca de Música.")

        web_search = re.match(
            r"(?:busca|buscame|investiga|consulta)(?: en internet| en google)?\s+(.+)",
            normalized,
        )
        if web_search:
            query = web_search.group(1).strip()
            if self._computer_tools.search_web(query):
                return Reply(f"He abierto una búsqueda sobre {query}.")
            return Reply("No he podido abrir la búsqueda.")

        volume = re.fullmatch(r"(?:pon )?(?:el )?volumen(?: al)? (\d{1,3})", normalized)
        if volume:
            level = max(0, min(100, int(volume.group(1))))
            if self._computer_tools.set_volume(level):
                return Reply(f"Volumen al {level} por ciento.")
            return Reply("No he podido cambiar el volumen.")

        reminder = re.search(
            r"recu[eé]rdame\s+(.+?)\s+(?:dentro de|en)\s+(\d+)\s+"
            r"(minutos?|horas?|d[ií]as?)",
            command,
            flags=re.IGNORECASE,
        )
        if reminder:
            title = reminder.group(1).strip(" .,!¿?¡")
            amount = min(365 * 24 * 60, int(reminder.group(2)))
            unit = self._normalize(reminder.group(3))
            if unit.startswith("minuto"):
                delay = timedelta(minutes=amount)
                spoken_delay = f"{amount} minutos"
            elif unit.startswith("dia"):
                delay = timedelta(days=amount)
                spoken_delay = f"{amount} días"
            else:
                delay = timedelta(hours=amount)
                spoken_delay = f"{amount} horas"
            due = datetime.now() + delay
            if self._computer_tools.create_reminder(title, due):
                return Reply(f"Recordatorio creado para dentro de {spoken_delay}.")
            return Reply("No he podido crear el recordatorio.")

        event = re.search(
            r"(?:crea|a[nñ]ade)(?: un)? evento(?: en el calendario)?\s+(.+?)\s+"
            r"(hoy|ma[nñ]ana)\s+a las\s+(\d{1,2})(?::(\d{2}))?",
            command,
            flags=re.IGNORECASE,
        )
        if event:
            title = event.group(1).strip(" .,!¿?¡")
            start = datetime.now()
            if self._normalize(event.group(2)) == "manana":
                start += timedelta(days=1)
            start = start.replace(
                hour=min(23, int(event.group(3))),
                minute=min(59, int(event.group(4) or 0)),
                second=0,
                microsecond=0,
            )
            if self._computer_tools.create_calendar_event(
                title, start, start + timedelta(hours=1)
            ):
                return Reply(f"Evento {title} añadido al calendario.")
            return Reply("No he podido crear el evento en el calendario.")
        return None

    @staticmethod
    def _extract_name(command: str, normalized: str) -> str | None:
        prefixes = ("me llamo ", "mi nombre es ")
        for prefix in prefixes:
            if normalized.startswith(prefix):
                name = command.strip()[len(prefix) :].strip(" .,!¿?¡")
                if name and len(name) <= 60:
                    return name
        return None

    @staticmethod
    def _normalize(command: str) -> str:
        """Iguala mayúsculas, acentos y puntuación producida por voz."""
        decomposed = unicodedata.normalize("NFKD", command.casefold())
        without_accents = "".join(
            character
            for character in decomposed
            if not unicodedata.combining(character)
        )
        words_only = re.sub(r"[^\w]+", " ", without_accents, flags=re.UNICODE)
        return " ".join(words_only.split())
