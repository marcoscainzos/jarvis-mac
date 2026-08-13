from jarvis.assistant import Assistant


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

