from jarvis.local_ai import OllamaAI


def test_detects_repetitive_conversation_loop() -> None:
    ai = OllamaAI()
    system = ai._messages[0]
    repeated = "¡Genial! ¿Qué acción deseas realizar dentro del directorio CPE?"
    ai._messages = [
        system,
        {"role": "user", "content": "abre CPE"},
        {"role": "assistant", "content": repeated},
        {"role": "user", "content": "duerme"},
        {"role": "assistant", "content": repeated.replace("¡Genial!", "¡Claro!")},
        {"role": "user", "content": "otra cosa"},
        {"role": "assistant", "content": repeated},
    ]

    assert ai._conversation_is_stuck() is True


def test_detects_semantically_repetitive_answers_on_second_turn() -> None:
    first = "¿Qué tipo de ayuda o servicio estás buscando?"
    second = "Entiendo. ¿Qué tipo de ayuda o servicio necesitas?"

    assert OllamaAI._similar(first, second) > 0.70
