from __future__ import annotations

import argparse

from jarvis.audio import SpeechError
from jarvis.assistant import Assistant
from jarvis.macos import open_application
from jarvis.macos_speech import MacOSSpeaker
from jarvis.speech import LocalWhisperListener


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Jarvis para macOS")
    parser.add_argument(
        "--voice", action="store_true", help="escuchar y responder usando la voz"
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    assistant = Assistant(open_application)
    listener = LocalWhisperListener() if args.voice else None
    speaker = MacOSSpeaker() if args.voice else None
    mode = "pulsa Intro para hablar" if args.voice else "escribe una orden"
    print(f"Jarvis v0.2 — {mode} o “salir” para terminar.")

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
            print("\nJarvis: Hasta pronto.")
            break
        except SpeechError as error:
            print(f"Jarvis: {error}")
            continue

        reply = assistant.handle(command)
        print(f"Jarvis: {reply.message}")
        if speaker:
            speaker.speak(reply.message)
        if reply.should_exit:
            break


if __name__ == "__main__":
    main()
