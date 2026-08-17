from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
import re
import sqlite3
from typing import Protocol
import unicodedata
from urllib.error import URLError
from urllib.request import Request, urlopen


class ConversationalAI(Protocol):
    def reply(self, message: str) -> str: ...

    def plan_action(self, message: str) -> dict[str, str]: ...

    def understand(self, message: str, context: dict[str, str]) -> dict[str, str]: ...

    def summarize_research(
        self, query: str, sources: list[dict[str, str]]
    ) -> str: ...

    def summarize_project_session(self, context: str) -> str: ...


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

    def clear(self) -> None:
        with self._connect() as connection:
            connection.execute("DELETE FROM conversation")


class OllamaAI:
    """Cliente local para conversar con un modelo servido por Ollama."""

    def __init__(
        self,
        model: str = "qwen3:1.7b",
        reasoning_model: str = "qwen3.5:4b",
        action_model: str = "qwen3:1.7b",
        endpoint: str = "http://127.0.0.1:11434/api/chat",
        history_path: Path | None = None,
    ) -> None:
        self.model = model
        self.reasoning_model = reasoning_model
        self.action_model = action_model
        self.endpoint = endpoint
        self._history = ConversationHistory(history_path) if history_path else None
        self._messages: list[dict[str, str]] = [
            {
                "role": "system",
                "content": (
                    "Eres Jarvis, un asistente personal útil, prudente y conversacional. "
                    "Responde siempre en español claro. Como la respuesta se leerá en voz "
                    "alta, responde normalmente en un máximo de dos frases breves y no uses markdown. "
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
        return self._reply(message, "")

    def reply_with_context(self, message: str, context: str) -> str:
        return self._reply(message, context)

    def _reply(self, message: str, context: str) -> str:
        if self._conversation_is_stuck():
            self._messages = [self._messages[0]]
            if self._history is not None:
                self._history.clear()
        context_message = (
            [{"role": "system", "content": "Memoria local relevante del usuario:\n" + context}]
            if context else []
        )
        messages = [*self._messages, *context_message, {"role": "user", "content": message}]
        payload = json.dumps(
            {
                "model": self.reasoning_model if self._needs_reasoning(message) else self.model,
                "messages": messages,
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.6,
                    "num_ctx": 4096,
                    "num_predict": 100,
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
        previous_answers = [
            item["content"] for item in self._messages[-6:]
            if item["role"] == "assistant"
        ]
        if previous_answers and self._similar(answer, previous_answers[-1]) > 0.70:
            # No guardamos otra copia: limpiamos el anclaje y respondemos al turno actual.
            self._messages = [self._messages[0]]
            if self._history is not None:
                self._history.clear()
            retry_messages = [
                self._messages[0],
                {
                    "role": "system",
                    "content": "Responde exclusivamente a la petición actual. No repitas respuestas anteriores.",
                },
                *context_message,
                {"role": "user", "content": message},
            ]
            answer = self._request_chat(retry_messages, think=False)
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

    def understand(self, message: str, context: dict[str, str]) -> dict[str, str]:
        """Distingue conversación y acciones usando el historial, no frases rígidas."""
        schema = {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["conversation", "action", "fallback"]},
                "response": {"type": "string"},
                "action": {"type": "string", "enum": ["open_app", "web_search", "youtube", "list_files", "find_file", "open_file", "create_folder", "move_file", "rename_file", "trash_file", "none"]},
                "target": {"type": "string"},
                "location": {"type": "string", "enum": ["desktop", "downloads", "documents"]},
                "destination": {"type": "string", "enum": ["desktop", "downloads", "documents"]},
                "new_name": {"type": "string"},
            },
            "required": ["kind", "response", "action", "target", "location", "destination", "new_name"],
        }
        system = (
            "Comprende la intención real de la última frase dentro de la conversación. "
            "Devuelve kind=action solo si el usuario pide explícitamente hacer algo en su "
            "ordenador: abrir, buscar, reproducir, mostrar, crear, mover, renombrar o borrar. "
            "Usa kind=fallback para órdenes especiales como pantalla, investigación, tareas, "
            "calendario, recordatorios, volumen, dormir o salir. En cualquier otro caso usa "
            "kind=conversation y redacta en response una contestación natural en español, "
            "breve para voz, que responda al significado y contexto; no uses frases de plantilla. "
            "Para kind=action completa action con open_app, web_search, youtube, list_files, "
            "find_file, open_file, create_folder, move_file, rename_file o trash_file; target es "
            "el objeto concreto y location/destination solo desktop, downloads o documents. "
            "No afirmes que realizaste una acción. Contexto local: " + json.dumps(context, ensure_ascii=False)
        )
        messages = [
            {"role": "system", "content": system},
            *self._messages[-10:],
            {"role": "user", "content": message},
        ]
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {"temperature": 0.25, "num_ctx": 4096, "num_predict": 140},
            }
        ).encode("utf-8")
        request = Request(self.endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
            understood = json.loads(result.get("message", {}).get("content", "{}"))
        except (OSError, URLError, TimeoutError, ValueError, TypeError):
            return {"kind": "fallback", "response": ""}
        kind = str(understood.get("kind", "fallback"))
        response_text = str(understood.get("response", "")).strip()[:1000]
        if kind == "conversation" and response_text:
            self._store_exchange(message, response_text)
            return {"kind": kind, "response": response_text}
        if kind == "action":
            return {
                "kind": "action", "response": "",
                "action": str(understood.get("action", "none")),
                "target": str(understood.get("target", ""))[:500],
                "location": str(understood.get("location", "documents")),
                "destination": str(understood.get("destination", "documents")),
                "new_name": str(understood.get("new_name", ""))[:150],
            }
        return {"kind": "fallback", "response": ""}

    def warm_up(self) -> None:
        payload = json.dumps({"model": self.model, "prompt": "", "keep_alive": "30m"}).encode("utf-8")
        endpoint = self.endpoint.rsplit("/", 1)[0] + "/generate"
        try:
            with urlopen(Request(endpoint, data=payload, headers={"Content-Type": "application/json"}, method="POST"), timeout=90):
                pass
        except (OSError, URLError, TimeoutError):
            pass

    def _store_exchange(self, message: str, answer: str) -> None:
        self._messages.extend([{"role": "user", "content": message}, {"role": "assistant", "content": answer}])
        if self._history is not None:
            self._history.append("user", message)
            self._history.append("assistant", answer)
        self._messages = [self._messages[0], *self._messages[1:][-20:]]

    def analyze_screen(self, visible_text: str, question: str) -> str:
        """Interpreta OCR local sin incorporar su contenido al historial permanente."""
        prompt = (
            "Analiza el texto extraído de la ventana activa del usuario. Responde en "
            "español, de forma concreta y en un máximo de cuatro frases. Si hay un error, "
            "explica su causa probable y el siguiente paso. No inventes elementos que no "
            "aparezcan en el texto.\n\nPetición: " + question +
            "\n\nTexto visible:\n" + visible_text[:12_000]
        )
        return self._request_chat([self._messages[0], {"role": "user", "content": prompt}], think=False)

    def summarize_project_session(self, context: str) -> str:
        prompt = (
            "Resume esta sesión de proyecto en español y en un máximo de tres frases: qué se "
            "observó, qué problemas aparecieron y cuál debería ser el siguiente paso. No inventes "
            "actividad que no figure en el registro.\n\n" + context[:8000]
        )
        return self._request_chat(
            [self._messages[0], {"role": "user", "content": prompt}], think=False
        )

    def _conversation_is_stuck(self) -> bool:
        answers = [
            item["content"] for item in self._messages[-8:]
            if item["role"] == "assistant"
        ][-3:]
        return len(answers) == 3 and all(
            self._similar(answers[index], answers[index + 1]) > 0.65
            for index in range(2)
        )

    @staticmethod
    def _similar(first: str, second: str) -> float:
        return SequenceMatcher(None, first.casefold(), second.casefold()).ratio()

    def _request_chat(self, messages: list[dict[str, str]], think: bool) -> str:
        payload = json.dumps(
            {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "think": think,
                "keep_alive": "30m",
                "options": {"temperature": 0.65, "num_ctx": 4096, "num_predict": 160},
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
        return answer

    def plan_action(self, message: str) -> dict[str, str]:
        """Traduce lenguaje natural a una acción limitada y verificable."""
        system = (
            "Convierte la petición en UNA acción segura de ordenador. Devuelve solo JSON. "
            "Acciones: open_app, web_search, youtube, list_files, find_file, open_file, "
            "create_folder, move_file, rename_file, trash_file o none. target contiene la "
            "aplicación, consulta, archivo o carpeta. destination es la carpeta de destino para "
            "move_file y new_name es el nombre completo nuevo para rename_file. "
            "location solo puede ser desktop, downloads o documents; 'bajé', 'descargué' y "
            "'lo último que bajé' significan downloads. Usa list_files solo para preguntar qué "
            "hay o qué es reciente; usa find_file para localizar y open_file para abrir. "
            "Si no se indica ubicación usa documents. "
            "trash_file significa enviar a la Papelera, nunca borrar definitivamente. Nunca "
            "planifiques sobrescribir, instalar, ejecutar comandos, cambiar permisos, usar "
            "contraseñas, enviar mensajes o comprar: en esos casos usa none."
        )
        schema = {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": [
                        "open_app", "web_search", "youtube", "list_files",
                        "find_file", "open_file", "create_folder", "move_file",
                        "rename_file", "trash_file", "none",
                    ],
                },
                "target": {"type": "string"},
                "location": {
                    "type": "string",
                    "enum": ["desktop", "downloads", "documents"],
                },
                "destination": {
                    "type": "string",
                    "enum": ["desktop", "downloads", "documents"],
                },
                "new_name": {"type": "string"},
            },
            "required": ["action", "target", "location", "destination", "new_name"],
        }
        payload = json.dumps(
            {
                "model": self.action_model,
                "messages": [
                    {"role": "system", "content": system},
                    {
                        "role": "user",
                        "content": "Enséñame lo último que bajé",
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps({"action": "list_files", "target": "", "location": "downloads", "destination": "documents", "new_name": ""}),
                    },
                    {
                        "role": "user",
                        "content": "Encuentra el PDF del examen en el escritorio",
                    },
                    {
                        "role": "assistant",
                        "content": json.dumps({"action": "find_file", "target": "examen pdf", "location": "desktop", "destination": "documents", "new_name": ""}),
                    },
                    {"role": "user", "content": message},
                ],
                "format": schema,
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {"temperature": 0.1, "num_predict": 100},
            }
        ).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=60) as response:
                result = json.load(response)
            content = result.get("message", {}).get("content", "{}")
            plan = json.loads(content)
        except (OSError, URLError, TimeoutError, ValueError, TypeError):
            return {"action": "none", "target": "", "location": "documents"}
        allowed = {
            "open_app", "web_search", "youtube", "list_files", "find_file",
            "open_file", "create_folder", "move_file", "rename_file", "trash_file", "none",
        }
        action = str(plan.get("action", "none"))
        location = str(plan.get("location", "documents"))
        plain_message = "".join(
            character for character in unicodedata.normalize("NFKD", message.casefold())
            if not unicodedata.combining(character)
        )
        if "escritorio" in plain_message:
            location = "desktop"
        elif any(word in plain_message for word in ("descargas", "descargue", "baje")):
            location = "downloads"
        elif "documentos" in plain_message:
            location = "documents"
        target = str(plan.get("target", ""))[:500].strip()
        target = re.sub(
            r"\s+(?:de|del|en)\s+(?:mi\s+)?(?:escritorio|descargas|documentos)\b",
            "",
            target,
            flags=re.IGNORECASE,
        ).strip()
        words = target.split()
        target = " ".join(
            word for index, word in enumerate(words)
            if index == 0 or word.casefold() != words[index - 1].casefold()
        )
        return {
            "action": action if action in allowed else "none",
            "target": target,
            "location": location if location in {"desktop", "downloads", "documents"} else "documents",
            "destination": str(plan.get("destination", "documents"))
            if str(plan.get("destination", "documents")) in {"desktop", "downloads", "documents"}
            else "documents",
            "new_name": str(plan.get("new_name", ""))[:150],
        }

    def summarize_research(
        self, query: str, sources: list[dict[str, str]]
    ) -> str:
        evidence = "\n\n".join(
            f"FUENTE {index}: {source['title']}\nURL: {source['url']}\n"
            f"CONTENIDO: {source['text']}"
            for index, source in enumerate(sources, start=1)
        )
        payload = json.dumps(
            {
                "model": self.reasoning_model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "Eres el investigador de Jarvis. Compara las fuentes y responde en "
                            "español con conclusiones concretas. No inventes datos; si las fuentes "
                            "no bastan, dilo. Menciona los números de fuente que respaldan cada "
                            "conclusión. Da primero una respuesta breve apta para voz."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"Pregunta: {query}\n\n{evidence[:24000]}",
                    },
                ],
                "stream": False,
                "think": True,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0.3,
                    "num_ctx": 8192,
                    "num_predict": 420,
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
            with urlopen(request, timeout=180) as response:
                result = json.load(response)
        except (OSError, URLError, TimeoutError) as error:
            raise RuntimeError("La IA local no ha podido resumir las fuentes.") from error
        answer = str(result.get("message", {}).get("content", "")).strip()
        if not answer:
            raise RuntimeError("La investigación terminó sin conclusiones.")
        answer = re.sub(r"[*#_`]+", "", answer)
        answer = re.sub(r"\[(.*?)\]\([^)]*\)", r"\1", answer)
        return " ".join(answer.split())

    @staticmethod
    def _needs_reasoning(message: str) -> bool:
        lowered = message.casefold()
        reasoning_cues = (
            "por qué",
            "por que",
            "explica",
            "analiza",
            "razona",
            "compara",
            "ayúdame a",
            "ayudame a",
            "qué harías",
            "que harias",
        )
        if any(cue in lowered for cue in reasoning_cues):
            return True
        return len(lowered.split()) >= 8 and any(
            cue in lowered for cue in ("cómo ", "como ", "qué debería", "que deberia")
        )
