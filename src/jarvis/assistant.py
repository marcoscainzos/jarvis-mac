from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import re
from typing import Callable
import unicodedata

from jarvis.memory import Memory, VolatileMemory
from jarvis.local_ai import ConversationalAI
from jarvis.computer_tools import ComputerTools
from jarvis.research import BackgroundResearcher
from jarvis.task_engine import TaskEngine


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
        researcher: BackgroundResearcher | None = None,
        task_engine: TaskEngine | None = None,
    ) -> None:
        self._open_app = open_app
        self._memory = memory or VolatileMemory()
        self._conversational_ai = conversational_ai
        self._computer_tools = computer_tools
        self._researcher = researcher
        self._task_engine = task_engine
        self._pending_plan: dict[str, str] | None = None

    def handle(self, command: str) -> Reply:
        normalized = self._normalize(command)

        if not normalized:
            return Reply("No he oído ninguna orden.")
        if any(
            word in normalized.split()
            for word in ("duerme", "duermete", "durme", "durmete")
        ):
            return Reply("Entendido. Quedo a la espera de las palmadas.", should_exit=True)
        if self._pending_plan is not None:
            if normalized in {"si", "sí", "confirma", "si confirma", "adelante", "hazlo"}:
                plan = self._pending_plan
                self._pending_plan = None
                return self._execute_sensitive_plan(plan)
            if normalized in {"no", "cancela", "cancelar", "dejalo", "déjalo"}:
                self._pending_plan = None
                return Reply("De acuerdo, operación cancelada.")
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
                "buscar en internet, controlar la música, gestionar archivos y crear "
                "recordatorios o eventos. Puedo entender referencias como ábrelo y pediré "
                "confirmación antes de mover, renombrar o enviar algo a la Papelera."
            )
        if normalized in {"que hora es", "hora"}:
            return Reply(f"Son las {datetime.now():%H:%M}.")
        task_reply = self._handle_task(command, normalized)
        if task_reply is not None:
            return task_reply
        research_reply = self._handle_research(command, normalized)
        if research_reply is not None:
            return research_reply
        screen_reply = self._handle_screen(command, normalized)
        if screen_reply is not None:
            return screen_reply
        action_reply = self._handle_computer_action(command, normalized)
        if action_reply is not None:
            return action_reply
        directory = re.search(
            r"(?:abre|abrir)\s+(?:el\s+)?(?:directorio|carpeta)\s+(.+)", normalized
        )
        if directory and self._computer_tools is not None:
            target = directory.group(1).strip()
            requested_location = next(
                (
                    location for cue, location in (
                        ("escritorio", "desktop"),
                        ("descargas", "downloads"),
                        ("documentos", "documents"),
                    )
                    if cue in target
                ),
                None,
            )
            target = re.sub(r"\s+(?:del?|en)\s+(?:escritorio|descargas|documentos)$", "", target)
            locations = [requested_location] if requested_location else ["desktop", "downloads", "documents"]
            for location in locations:
                path = self._computer_tools.open_file(target, location)
                if path is not None:
                    self._remember_file(path, location)
                    return Reply(f"He abierto {path.name}.")
            return Reply(f"No encuentro el directorio {target} en tus carpetas personales.")
        file_opening = any(
            cue in normalized
            for cue in ("archivo", "documento", "pdf", "carpeta", "abrelo", "abrela")
        )
        if normalized.startswith("abre ") and not file_opening:
            app_name = command.strip()[5:].strip()
            if not app_name:
                return Reply("Dime qué aplicación quieres abrir.")
            if self._open_app(app_name):
                return Reply(f"Abriendo {app_name}.")
            return Reply(
                f"No he encontrado la aplicación {app_name}."
            )

        planned_reply = self._handle_planned_action(command, normalized)
        if planned_reply is not None:
            return planned_reply

        if self._conversational_ai is not None:
            try:
                return Reply(self._conversational_ai.reply(command))
            except RuntimeError as error:
                return Reply(str(error))
        return Reply("Todavía no conozco esa orden.")

    def _handle_task(self, command: str, normalized: str) -> Reply | None:
        if self._task_engine is None:
            return None
        if normalized in {"cancela la tarea", "deten la tarea", "para la tarea"}:
            if self._task_engine.cancel():
                return Reply("He cancelado la tarea. No ejecutaré los pasos pendientes.")
            return Reply("No hay ninguna tarea activa que cancelar.")
        if normalized in {"como va la tarea", "estado de la tarea", "que estas haciendo"}:
            task = self._task_engine.status()
            if task.state == "idle":
                return Reply("No tengo ninguna tarea activa.")
            if task.state == "done":
                return Reply(f"La tarea terminó y verifiqué el resultado en {task.output}.")
            if task.state == "error":
                return Reply(f"La tarea se detuvo en {task.step}: {task.error}.")
            return Reply(f"Estoy con {task.goal}; ahora mismo: {task.step}.")
        wants_report = any(cue in normalized for cue in ("crea un informe", "crea un documento", "haz un informe", "guarda un informe"))
        wants_research = any(cue in normalized for cue in ("investiga", "compara", "averigua"))
        if not (wants_report and wants_research):
            return None
        location = "downloads" if "descargas" in normalized else "documents" if "documentos" in normalized else "desktop"
        query = re.sub(r"(?:y |, )?(?:crea|haz|guarda) un (?:informe|documento).*$", "", normalized).strip()
        query = re.sub(r"^(?:investiga|compara|averigua)\s+", "", query).strip()
        if self._task_engine.start_research_report(query, location):
            return Reply("He creado una tarea verificable. Investigaré, compararé las fuentes y guardaré el informe; puedes preguntarme cómo va o decir cancela la tarea.")
        return Reply("Ya hay una tarea o investigación en marcha. Puedes preguntarme cómo va.")

    def _handle_screen(self, command: str, normalized: str) -> Reply | None:
        click = re.search(r"(?:pulsa|haz clic en|pincha en)\s+(?:el |la )?(.+)", normalized)
        if click:
            target = click.group(1).strip()
            sensitive = ("comprar", "pagar", "enviar", "borrar", "eliminar", "contrasena", "contraseña")
            if any(word in target for word in sensitive):
                return Reply("No pulsaré controles de compra, pago, envío, borrado o contraseñas.")
            if self._computer_tools is None:
                return Reply("No tengo acceso visual a esa ventana.")
            if self._computer_tools.click_visible_text(target):
                return Reply(f"He pulsado {target}.")
            return Reply(f"No encuentro un elemento visible llamado {target}.")
        cues = (
            "que hay en pantalla", "que ves", "mira mi pantalla", "mira la pantalla",
            "lee la pantalla", "analiza la pantalla", "analiza esta ventana",
            "explica este error", "que pone en la pantalla", "captura la pantalla",
            "captura esta ventana", "haz una captura",
        )
        if not any(cue in normalized for cue in cues):
            return None
        if self._computer_tools is None:
            return Reply("No tengo acceso a la ventana activa.")
        if normalized.startswith(("captura", "haz una captura")):
            path = self._computer_tools.capture_active_window()
            if path is None:
                return Reply("No he podido guardar la captura. Revisa el permiso de Grabación de pantalla.")
            return Reply(f"He guardado la captura en Imágenes, dentro de Jarvis, como {path.name}.")
        path, visible_text = self._computer_tools.read_active_window()
        if path is None:
            return Reply(
                "No he podido capturar la ventana. Activa Jarvis en Privacidad y seguridad, Grabación de pantalla."
            )
        if not visible_text.strip():
            return Reply(
                "He capturado la ventana, pero no puedo leer texto. Comprueba el permiso de Grabación de pantalla."
            )
        analyzer = getattr(self._conversational_ai, "analyze_screen", None)
        if analyzer is None:
            preview = " ".join(visible_text.split())[:350]
            return Reply(f"En la ventana puedo leer: {preview}")
        try:
            return Reply(analyzer(visible_text, command))
        except RuntimeError as error:
            return Reply(str(error))

    def _handle_research(self, command: str, normalized: str) -> Reply | None:
        if self._researcher is None:
            return None
        status_questions = {
            "como va la investigacion", "que tal va la investigacion",
            "estado de la investigacion", "has terminado", "ya has terminado",
        }
        if normalized in status_questions:
            state, detail = self._researcher.status()
            if state == "running":
                return Reply(f"Sigo trabajando; ahora estoy {detail}.")
            if state == "done":
                return Reply("Ya he terminado. Pregúntame qué he encontrado para oír las conclusiones.")
            if state == "error":
                return Reply(f"La investigación se detuvo: {detail}.")
            return Reply("No tengo ninguna investigación en curso.")
        result_questions = {
            "que has encontrado", "que encontraste", "dime el resultado",
            "resultado de la investigacion", "conclusiones de la investigacion",
        }
        if normalized in result_questions:
            result = self._researcher.result()
            if result is None:
                state, detail = self._researcher.status()
                if state == "running":
                    return Reply(f"Todavía estoy {detail}.")
                return Reply("Aún no tengo una investigación terminada.")
            return Reply(result.summary)
        if normalized in {
            "que fuentes usaste", "cuales son las fuentes", "fuentes de la investigacion",
        }:
            result = self._researcher.result()
            if result is None:
                return Reply("Aún no tengo fuentes de una investigación terminada.")
            titles = ", ".join(title for title, _url in result.sources[:5])
            return Reply(f"He consultado estas fuentes: {titles}.")
        request = re.search(
            r"(?:investiga|investigues|investigar|averigua|compara|haz una investigacion (?:sobre|de))\s+(.+)",
            normalized,
        )
        if request:
            query = request.group(1).strip()
            if self._researcher.start(query):
                return Reply(
                    f"Empiezo a investigar {query} en segundo plano. Puedes seguir hablando conmigo o usando el Mac."
                )
            return Reply("Ya tengo una investigación en marcha. Pídeme su estado cuando quieras.")
        return None

    def _handle_planned_action(self, command: str, normalized: str) -> Reply | None:
        if self._computer_tools is None or self._conversational_ai is None:
            return None
        blocked = (
            "formatea", "contrasena", "contraseña", "password",
            "permiso", "instala", "desinstala", "terminal", "ejecuta comando",
            "compra", "paga",
        )
        if any(cue in normalized for cue in blocked):
            return Reply(
                "Esa operación puede afectar a datos, permisos o seguridad. No la ejecutaré sin un sistema de confirmación específico."
            )
        action_cues = (
            "abre", "inicia", "lanza", "busca", "encuentra", "localiza", "muestra",
            "ensena", "enseña", "ensename", "muéstrame", "que hay", "qué hay",
            "baje", "descargue", "crea una carpeta", "nueva carpeta", "mueve",
            "traslada", "renombra", "cambia el nombre", "papelera", "borra", "elimina",
            "youtube", "safari", "internet", "escritorio", "descargas", "documentos",
        )
        if not any(cue in normalized for cue in action_cues):
            return None
        planner = getattr(self._conversational_ai, "plan_action", None)
        if planner is None:
            return None
        plan = planner(command)
        action = plan.get("action", "none")
        target = plan.get("target", "").strip()
        location = plan.get("location", "documents")
        if normalized in {"abrelo", "abrela", "muestralo", "muestrala"}:
            target = self._memory.get("last_file_name") or target
            location = self._memory.get("last_file_location") or location
        if self._normalize(target) in {"lo", "la", "eso", "ese archivo", "esa carpeta"}:
            target = self._memory.get("last_file_name") or ""
            location = self._memory.get("last_file_location") or location
        place_names = {
            "desktop": "el Escritorio",
            "downloads": "Descargas",
            "documents": "Documentos",
        }
        place = place_names.get(location, "Documentos")

        if action == "open_app" and target:
            if self._open_app(target):
                return Reply(f"Ya tienes {target} abierto.")
            return Reply(f"No encuentro una aplicación llamada {target}.")
        if action == "web_search" and target:
            if self._computer_tools.search_web(target):
                return Reply(f"Te he dejado los resultados de {target} en Safari.")
            return Reply("Safari no ha podido abrir la búsqueda.")
        if action == "youtube" and target:
            if self._computer_tools.play_music(target):
                return Reply(f"Listo, he puesto {target} en YouTube.")
            return Reply("YouTube no ha respondido; prueba otra vez en un momento.")
        if action == "list_files":
            names = self._computer_tools.list_files(location)
            if not names:
                return Reply(f"No veo archivos en {place}.")
            preview = ", ".join(names[:5])
            return Reply(f"Lo más reciente en {place} es: {preview}.")
        if action == "find_file" and target:
            path = self._computer_tools.find_file(target, location)
            if path is None:
                return Reply(f"No encuentro {target} en {place}.")
            self._remember_file(path, location)
            return Reply(f"He encontrado {path.name} en {place}.")
        if action == "open_file" and target:
            path = self._computer_tools.open_file(target, location)
            if path is None:
                return Reply(f"No encuentro {target} en {place}.")
            self._remember_file(path, location)
            return Reply(f"Aquí tienes {path.name}.")
        if action == "create_folder" and target:
            path = self._computer_tools.create_folder(target, location)
            if path is None:
                return Reply(f"No he podido crear esa carpeta en {place}.")
            return Reply(f"Carpeta {path.name} creada en {place}.")
        if action in {"move_file", "rename_file", "trash_file"} and target:
            plan["target"] = target
            self._pending_plan = plan
            descriptions = {
                "move_file": f"mover {target}",
                "rename_file": f"renombrar {target} como {plan.get('new_name', '')}",
                "trash_file": f"enviar {target} a la Papelera",
            }
            return Reply(
                f"Voy a {descriptions[action]}. Di confirma para continuar o cancela para detenerme."
            )
        return None

    def _execute_sensitive_plan(self, plan: dict[str, str]) -> Reply:
        if self._computer_tools is None:
            return Reply("La herramienta ya no está disponible.")
        action = plan.get("action", "none")
        target = plan.get("target", "")
        location = plan.get("location", "documents")
        if action == "move_file":
            destination = plan.get("destination", "documents")
            path = self._computer_tools.move_file(target, location, destination)
            if path is not None:
                self._remember_file(path, destination)
                return Reply(f"He movido {path.name} correctamente.")
            return Reply("No he podido moverlo; puede que ya exista otro archivo con ese nombre.")
        if action == "rename_file":
            new_name = plan.get("new_name", "")
            path = self._computer_tools.rename_file(target, location, new_name)
            if path is not None:
                self._remember_file(path, location)
                return Reply(f"Listo, ahora se llama {path.name}.")
            return Reply("No he podido cambiar el nombre sin sobrescribir otro archivo.")
        if action == "trash_file":
            if self._computer_tools.trash_file(target, location):
                self._memory.forget("last_file_name")
                self._memory.forget("last_file_location")
                return Reply("He enviado el archivo a la Papelera; todavía puedes recuperarlo.")
            return Reply("No he podido enviar ese archivo a la Papelera.")
        return Reply("La operación pendiente ya no es válida.")

    def _remember_file(self, path: object, location: str) -> None:
        name = getattr(path, "name", "")
        if name:
            self._memory.set("last_file_name", str(name))
            self._memory.set("last_file_location", location)

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
                    return Reply(f"He abierto {query} en YouTube.")
                return Reply(f"No he podido buscar {query} en YouTube.")

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
