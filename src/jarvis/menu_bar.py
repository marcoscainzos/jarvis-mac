from __future__ import annotations

import threading
import time
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
    from PyObjCTools import AppHelper

    from jarvis.overlay import JarvisOverlay

    NSApplication.sharedApplication().setActivationPolicy_(
        NSApplicationActivationPolicyAccessory
    )

    class JarvisMenuBar(rumps.App):
        def __init__(self) -> None:
            super().__init__("J", title="◉", quit_button=None)
            memory = SQLiteMemory(Path.home() / ".jarvis" / "memory.db")
            self.service = JarvisService(
                Assistant(open_application, memory),
                LocalWhisperListener(
                    duration=4,
                    on_recorded=lambda: AppHelper.callAfter(
                        self._apply_status, "processing"
                    ),
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
            self.hotkeys = keyboard.GlobalHotKeys(
                {"<ctrl>+<alt>+<space>": self.start_listening}
            )
            self.hotkeys.start()
            self.overlay.show("ready")

        def start_listening(self, _sender: Any = None) -> None:
            if not self.listening_lock.acquire(blocking=False):
                return
            AppHelper.callAfter(self._begin_visual_listening)
            threading.Thread(target=self._listen_worker, daemon=True).start()

        def _listen_worker(self) -> None:
            try:
                time.sleep(0.6)
                command = self.service.listener.listen()
                reply = self.service.assistant.handle(command)
                AppHelper.callAfter(self._apply_status, "speaking")
                self.service.speaker.speak(reply.message)
                AppHelper.callAfter(
                    self._show_reply,
                    f"Tú: {command}\n\nJarvis: {reply.message}",
                )
            except SpeechError as error:
                AppHelper.callAfter(self._show_error, str(error))
            except Exception as error:
                AppHelper.callAfter(
                    self._show_error, f"Error inesperado: {error}"
                )
            finally:
                AppHelper.callAfter(self._apply_status, "ready")
                self.listening_lock.release()

        def _show_reply(self, message: str) -> None:
            rumps.notification("Jarvis", "Orden completada", message)

        def _show_error(self, message: str) -> None:
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
            self.overlay.hide()
            rumps.quit_application()

    JarvisMenuBar().run()


if __name__ == "__main__":
    main()
