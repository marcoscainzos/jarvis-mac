from __future__ import annotations

import json
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class ConversationalAI(Protocol):
    def reply(self, message: str) -> str: ...


class OllamaAI:
    """Cliente local para conversar con un modelo servido por Ollama."""

    def __init__(
        self,
        model: str = "qwen3:1.7b",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self._messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Eres Jarvis, un asistente personal útil, prudente y conversacional. "
                    "Responde siempre en español claro. Como la respuesta se leerá en voz "
                    "alta, responde normalmente en un máximo de tres frases y no uses markdown. "
                    "No afirmes haber realizado acciones "
                    "en el ordenador si no se te ha proporcionado una herramienta para ello."
                ),
            }
        ]

    def reply(self, message: str) -> str:
        messages = [*self._messages, {"role": "user", "content": message}]
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.6,
                    "num_ctx": 4096,
                    "num_predict": 160,
                },
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=120) as response:
                result = json.load(response)
        except (OSError, URLError, TimeoutError) as error:
            raise RuntimeError(
                "La inteligencia local no está disponible. Comprueba que Ollama esté iniciado."
            ) from error

        answer = str(result.get("message", {}).get("content", "")).strip()
        if not answer:
            raise RuntimeError("La inteligencia local no ha generado una respuesta.")
        self._messages.extend(
            [
                {"role": "user", "content": message},
                {"role": "assistant", "content": answer},
            ]
        )
        self._messages = [self._messages[0], *self._messages[-10:]]
        return answer
