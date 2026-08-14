from __future__ import annotations

import queue
import threading
from pathlib import Path
from typing import Any

from jarvis.app_service import JarvisService
from jarvis.assistant import Assistant
from jarvis.audio import SpeechError
from jarvis.macos import open_application
from jarvis.macos_speech import MacOSSpeaker
from jarvis.memory import SQLiteMemory
from jarvis.speech import LocalWhisperListener


def _load_desktop_dependencies() -> tuple[Any, Any]:
    try:
        import rumps
        from pynput import keyboard
    except ImportError as error:
        raise SystemExit(
            "Falta la interfaz de macOS. Instálala con: "
            "python -m pip install '.[voice,mac-app]'"
        ) from error
    return rumps, keyboard


def main() -> None:
    rumps, keyboard = _load_desktop_dependencies()
    from AppKit import NSApplication, NSApplicationActivationPolicyAccessory

    from jarvis.overlay import JarvisOverlay

    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory
    )

    class JarvisMenuBar(rumps.App):
        def __init__(self) -> None:
            super().__init__("J", title="◉", quit_button=None)
            self.events: queue.Queue[tuple[str, str]] = queue.Queue()
            memory = SQLiteMemory(Path.home() / ".jarvis" / "memory.db")
            self.service = JarvisService(
                Assistant(open_application, memory),
                LocalWhisperListener(
                    duration=4,
                    on_recorded=lambda: self.events.put(("status", "processing")),
                ),
                MacOSSpeaker(),
            )
            self.status = rumps.MenuItem("Estado: listo")
            self.overlay = JarvisOverlay()
            self.listen_item = rumps.MenuItem(
                "Escuchar (habla tras el sonido)  ⌃⌥Espacio",
                callback=self.start_listening,
            )
            self.menu = [
                self.status,
                None,
                self.listen_item,
                rumps.MenuItem("Salir de Jarvis", callback=self.quit_app),
            ]
            self.listening_lock = threading.Lock()
            self.timer = rumps.Timer(self.process_events, 0.2)
            self.timer.start()
            self.hotkeys = keyboard.GlobalHotKeys(
                {"<ctrl>+<alt>+<space>": self.start_listening}
            )
            self.hotkeys.start()
            self.overlay.show("ready")

        def start_listening(self, _sender: Any = None) -> None:
            if not self.listening_lock.acquire(blocking=False):
                return
            if _sender is None:
                self.events.put(("start", "listening"))
            else:
                self._begin_visual_listening()
            delay = threading.Timer(0.6, self._start_listening_worker)
            delay.daemon = True
            delay.start()

        def _start_listening_worker(self) -> None:
            threading.Thread(target=self._listen_worker, daemon=True).start()

        def _listen_worker(self) -> None:
            try:
                command = self.service.listener.listen()
                reply = self.service.assistant.handle(command)
                self.events.put(("status", "speaking"))
                self.service.speaker.speak(reply.message)
                self.events.put(("reply", f"Tú: {command}\n\nJarvis: {reply.message}"))
            except SpeechError as error:
                self.events.put(("error", str(error)))
            except Exception as error:
                self.events.put(("error", f"Error inesperado: {error}"))
            finally:
                self.events.put(("status", "ready"))
                self.listening_lock.release()

        def process_events(self, _timer: Any) -> None:
            while True:
                try:
                    event, message = self.events.get_nowait()
                except queue.Empty:
                    break
                if event == "status":
                    self._apply_status(message)
                elif event == "start":
                    self._begin_visual_listening()
                elif event == "reply":
                    rumps.notification("Jarvis", "Orden completada", message)
                elif event == "error":
                    self._apply_status("ready")
                    rumps.alert("Jarvis", message)

        def _begin_visual_listening(self) -> None:
            from AppKit import NSSound

            self._apply_status("listening")
            NSSound.beep()

        def _apply_status(self, state: str) -> None:
            labels = {
                "ready": "Estado: listo",
                "listening": "Estado: escuchando…",
                "processing": "Estado: procesando…",
                "speaking": "Estado: hablando…",
            }
            self.status.title = labels[state]
            self.title = "◉" if state == "ready" else "●"
            self.overlay.show(state)

        def quit_app(self, _sender: Any) -> None:
            self.hotkeys.stop()
            self.timer.stop()
            self.overlay.hide()
            rumps.quit_application()

    JarvisMenuBar().run()


if __name__ == "__main__":
    main()
