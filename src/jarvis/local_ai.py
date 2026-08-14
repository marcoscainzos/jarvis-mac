from __future__ import annotations

import json
from pathlib import Path
import sqlite3
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class ConversationalAI(Protocol):
    def reply(self, message: str) -> str: ...


class ConversationHistory:
    """Historial local persistente y acotado para conservar el contexto."""

    def __init__(self, path: Path, limit: int = 24) -> None:
        self.path = path
        self.limit = limit
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS conversation ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT NOT NULL, "
                "content TEXT NOT NULL, created_at TEXT DEFAULT CURRENT_TIMESTAMP)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)

    def recent(self) -> list[dict[str, str]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?",
                (self.limit,),
            ).fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]

    def append(self, role: str, content: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO conversation(role, content) VALUES (?, ?)",
                (role, content),
            )
            connection.execute(
                "DELETE FROM conversation WHERE id NOT IN "
                "(SELECT id FROM conversation ORDER BY id DESC LIMIT 100)"
            )


class OllamaAI:
    """Cliente local para conversar con un modelo servido por Ollama."""

    def __init__(
        self,
        model: str = "qwen3:1.7b",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        history_path: Path | None = None,
    ) -> None:
        self.model = model
        self.endpoint = endpoint
        self._history = ConversationHistory(history_path) if history_path else None
        self._messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Eres Jarvis, un asistente personal útil, prudente y conversacional. "
                    "Responde siempre en español claro. Como la respuesta se leerá en voz "
                    "alta, responde normalmente en un máximo de tres frases y no uses markdown. "
                    "Dirígete al usuario como señor de vez en cuando, pero no en todas las "
                    "respuestas. Mantén un tono masculino, elegante, calmado y profesional. "
                    "Recuerda lo dicho anteriormente, responde al significado de la última "
                    "frase y evita repetir literalmente respuestas anteriores. Si falta un "
                    "dato para ayudar o actuar, haz una sola pregunta concreta. Los datos que "
                    "el usuario te cuente pertenecen al usuario: no digas que son tuyos. "
                    "Conversa de "
                    "forma natural y toma iniciativa con sugerencias útiles cuando proceda. "
                    "No afirmes haber realizado acciones "
                    "en el ordenador si no se te ha proporcionado una herramienta para ello."
                ),
            }
        ]
        if self._history is not None:
            self._messages.extend(self._history.recent())

    def reply(self, message: str) -> str:
        messages = [*self._messages, {"role": "user", "content": message}]
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": self._needs_reasoning(message),
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
        if self._history is not None:
            self._history.append("user", message)
            self._history.append("assistant", answer)
        conversation = self._messages[1:]
        self._messages = [self._messages[0], *conversation[-20:]]
        return answer

    @staticmethod
    def _needs_reasoning(message: str) -> bool:
        lowered = message.casefold()
        reasoning_cues = (
            "por qué",
            "por que",
            "cómo",
            "como ",
            "explica",
            "analiza",
            "razona",
            "ayúdame a",
            "ayudame a",
            "qué harías",
            "que harias",
        )
        return any(cue in lowered for cue in reasoning_cues)
