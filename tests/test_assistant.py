from jarvis.assistant import Assistant
from jarvis.memory import VolatileMemory


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


def test_exit_command_ends_session() -> None:
    assistant = Assistant(lambda _: False)
    assert assistant.handle("salir").should_exit is True


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
