from jarvis.assistant import Assistant
from jarvis.memory import VolatileMemory
from pathlib import Path


class FakeTools:
    def __init__(self) -> None:
        self.calls: list[tuple] = []

    def control_music(self, action: str) -> bool:
        self.calls.append(("music", action))
        return True

    def set_volume(self, level: int) -> bool:
        self.calls.append(("volume", level))
        return True

    def play_music(self, query: str) -> bool:
        self.calls.append(("play_music", query))
        return True

    def search_web(self, query: str) -> bool:
        self.calls.append(("search_web", query))
        return True

    def list_files(self, location: str) -> list[str]:
        self.calls.append(("list_files", location))
        return ["informe.pdf", "foto.png"]

    def find_file(self, query: str, location: str):
        self.calls.append(("find_file", query, location))
        return Path("/tmp/informe.pdf")

    def open_file(self, query: str, location: str):
        self.calls.append(("open_file", query, location))
        return Path("/tmp/informe.pdf")

    def open_path(self, path: Path) -> bool:
        self.calls.append(("open_path", path))
        return True

    def create_folder(self, name: str, location: str):
        self.calls.append(("create_folder", name, location))
        return Path("/tmp") / name

    def move_file(self, query: str, source: str, destination: str):
        self.calls.append(("move_file", query, source, destination))
        return Path("/tmp") / query

    def rename_file(self, query: str, location: str, new_name: str):
        self.calls.append(("rename_file", query, location, new_name))
        return Path("/tmp") / new_name

    def trash_file(self, query: str, location: str) -> bool:
        self.calls.append(("trash_file", query, location))
        return True

    def create_reminder(self, title, due) -> bool:
        self.calls.append(("reminder", title, due))
        return True

    def create_calendar_event(self, title, start, end) -> bool:
        self.calls.append(("event", title, start, end))
        return True


class FakeAI:
    def reply(self, message: str) -> str:
        return f"Respuesta razonada a: {message}"


class FakePlannerAI(FakeAI):
    def __init__(self, plan: dict[str, str]) -> None:
        self.plan = plan

    def plan_action(self, message: str) -> dict[str, str]:
        return self.plan


def test_greets_user() -> None:
    assistant = Assistant(lambda _: False)
    assert assistant.handle("Hola Jarvis").message == "Hola. Estoy listo para ayudarte."


def test_opens_allowed_application() -> None:
    opened: list[str] = []
    assistant = Assistant(lambda app: not opened.append(app))

    reply = assistant.handle("abre Calculadora")

    assert opened == ["Calculadora"]
    assert reply.message == "Abriendo Calculadora."


def test_unknown_command_does_not_execute_action() -> None:
    opened: list[str] = []
    assistant = Assistant(lambda app: not opened.append(app))

    reply = assistant.handle("borra todos mis archivos")

    assert opened == []
    assert "Todavía no conozco" in reply.message


def test_unknown_command_uses_conversational_ai() -> None:
    assistant = Assistant(lambda _: False, conversational_ai=FakeAI())

    reply = assistant.handle("Explícame por qué el cielo es azul")

    assert reply.message.startswith("Respuesta razonada")


def test_controls_music_and_volume() -> None:
    tools = FakeTools()
    assistant = Assistant(lambda _: False, computer_tools=tools)

    assistant.handle("pon música")
    assistant.handle("pon el volumen al 35")

    assert tools.calls == [("music", "play_pause"), ("volume", 35)]


def test_creates_reminder_and_calendar_event() -> None:
    tools = FakeTools()
    assistant = Assistant(lambda _: False, computer_tools=tools)

    assistant.handle("recuérdame estudiar dentro de 2 horas")
    assistant.handle("crea un evento entrenamiento mañana a las 18:30")

    assert tools.calls[0][0:2] == ("reminder", "estudiar")
    assert tools.calls[1][0:2] == ("event", "entrenamiento")


def test_natural_music_search_and_web_search() -> None:
    tools = FakeTools()
    assistant = Assistant(lambda _: False, computer_tools=tools)

    music_reply = assistant.handle("pon música de Queen")
    assistant.handle("búscame restaurantes italianos en Vigo")

    assert tools.calls == [
        ("play_music", "queen"),
        ("search_web", "restaurantes italianos en vigo"),
    ]
    assert "YouTube" in music_reply.message


def test_creates_reminders_in_minutes_and_days() -> None:
    tools = FakeTools()
    assistant = Assistant(lambda _: False, computer_tools=tools)

    assistant.handle("recuérdame sacar la ropa en 20 minutos")
    assistant.handle("recuérdame llamar a Ana dentro de 2 días")

    assert [call[0:2] for call in tools.calls] == [
        ("reminder", "sacar la ropa"),
        ("reminder", "llamar a Ana"),
    ]


def test_ai_plans_natural_file_action() -> None:
    tools = FakeTools()
    ai = FakePlannerAI(
        {"action": "open_file", "target": "informe", "location": "downloads"}
    )
    assistant = Assistant(lambda _: False, conversational_ai=ai, computer_tools=tools)

    reply = assistant.handle("podrías localizar y abrir el informe de descargas")

    assert tools.calls == [("open_file", "informe", "downloads")]
    assert reply.message == "Aquí tienes informe.pdf."


def test_requires_confirmation_before_trashing_file() -> None:
    tools = FakeTools()
    ai = FakePlannerAI(
        {"action": "trash_file", "target": "informe", "location": "documents"}
    )
    assistant = Assistant(lambda _: False, conversational_ai=ai, computer_tools=tools)

    reply = assistant.handle("envía el informe de documentos a la papelera")

    assert tools.calls == []
    assert "confirma" in reply.message
    confirmed = assistant.handle("sí, confirma")
    assert tools.calls == [("trash_file", "informe", "documents")]
    assert "Papelera" in confirmed.message


def test_can_cancel_sensitive_action() -> None:
    tools = FakeTools()
    ai = FakePlannerAI(
        {"action": "move_file", "target": "informe", "location": "downloads", "destination": "documents"}
    )
    assistant = Assistant(lambda _: False, conversational_ai=ai, computer_tools=tools)

    assistant.handle("mueve el informe a documentos")
    reply = assistant.handle("cancela")

    assert tools.calls == []
    assert "cancelada" in reply.message


def test_exit_command_ends_session() -> None:
    assistant = Assistant(lambda _: False)
    assert assistant.handle("salir").should_exit is True
    assert assistant.handle("Jarvis, duerme").should_exit is True
    assert assistant.handle("Ya lo habéis durme").should_exit is True


def test_opens_named_directory_without_conversation_loop() -> None:
    tools = FakeTools()
    assistant = Assistant(lambda _: False, computer_tools=tools)

    reply = assistant.handle("Quiero solamente abrir el directorio CPE")

    assert tools.calls == [("open_file", "cpe", "desktop")]
    assert reply.message == "He abierto informe.pdf."


def test_remembers_and_forgets_name() -> None:
    memory = VolatileMemory()
    assistant = Assistant(lambda _: False, memory)

    assert "Marcos" in assistant.handle("me llamo Marcos").message
    assert assistant.handle("hola").message.startswith("Hola, Marcos.")
    assert "Marcos" in assistant.handle("qué sabes de mí").message

    assistant.handle("olvida mi nombre")
    assert assistant.handle("hola").message == "Hola. Estoy listo para ayudarte."


def test_rejects_unreasonably_long_name() -> None:
    assistant = Assistant(lambda _: False)
    reply = assistant.handle(f"me llamo {'x' * 61}")
    assert "Todavía no conozco" in reply.message


def test_understands_voice_punctuation_and_accents() -> None:
    assistant = Assistant(lambda _: False)

    assert "Puedo conversar" in assistant.handle("¿Qué puedes hacer?").message
    assert assistant.handle("¡Hola Jarvis!").message.startswith("Hola.")
    assert assistant.handle("¿Qué hora es?").message.startswith("Son las")


def test_accepts_common_jarvis_transcription() -> None:
    assistant = Assistant(lambda _: False)
    assert assistant.handle("Allervis.").message == "Sí, señor."
    assert assistant.handle("Jarvis").message == "Sí, señor."
