from __future__ import annotations

import argparse
from pathlib import Path

from jarvis.audio import SpeechError
from jarvis.assistant import Assistant
from jarvis.macos import MacOSComputerTools, open_application
from jarvis.local_ai import OllamaAI
from jarvis.macos_speech import MacOSSpeaker
from jarvis.memory import SQLiteMemory
from jarvis.speech import LocalWhisperListener


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Iris para macOS")
    parser.add_argument(
        "--voice", action="store_true", help="escuchar y responder usando la voz"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    memory = SQLiteMemory(Path.home() / ".jarvis" / "memory.db")
    assistant = Assistant(open_application, memory, OllamaAI(), MacOSComputerTools())
    listener = LocalWhisperListener() if args.voice else None
    speaker = MacOSSpeaker() if args.voice else None
    mode = "pulsa Intro para hablar" if args.voice else "escribe una orden"
    print(f"Iris v0.4 — {mode} o “salir” para terminar.")

    while True:
        try:
            if listener:
                input("Pulsa Intro y habla: ")
                print("Escuchando…")
                command = listener.listen()
                print(f"Tú: {command}")
            else:
                command = input("Tú: ")
        except (EOFError, KeyboardInterrupt):
            print("\nIris: Hasta pronto.")
            break
        except SpeechError as error:
            print(f"Iris: {error}")
            continue

        reply = assistant.handle(command)
        print(f"Iris: {reply.message}")
        if speaker:
            speaker.speak(reply.message)
        if reply.should_exit:
            break


if __name__ == "__main__":
    main()
