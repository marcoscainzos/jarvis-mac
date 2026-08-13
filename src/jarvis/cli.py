from __future__ import annotations

from jarvis.assistant import Assistant
from jarvis.macos import open_application


def main() -> None:
    assistant = Assistant(open_application)
    print("Jarvis v0.1 — escribe una orden o “salir” para terminar.")

    while True:
        try:
            command = input("Tú: ")
        except (EOFError, KeyboardInterrupt):
            print("\nJarvis: Hasta pronto.")
            break

        reply = assistant.handle(command)
        print(f"Jarvis: {reply.message}")
        if reply.should_exit:
            break


if __name__ == "__main__":
    main()

