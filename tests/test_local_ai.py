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
