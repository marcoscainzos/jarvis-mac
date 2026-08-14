from __future__ import annotations

import fcntl
import threading
from pathlib import Path
from typing import Any

from jarvis.app_service import JarvisService
from jarvis.assistant import Assistant
from jarvis.audio import NoSpeechTimeout, SpeechError
from jarvis.clap_detector import ClapDetector
from jarvis.login_item import disable_login, enable_login, is_login_enabled
from jarvis.local_ai import OllamaAI
from jarvis.macos import MacOSComputerTools, open_application
from jarvis.macos_speech import MacOSSpeaker
from jarvis.memory import SQLiteMemory
from jarvis.speech import LocalWhisperListener


def _acquire_single_instance() -> Any | None:
    lock_path = Path.home() / ".jarvis" / "app.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("w")
    try:
        fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        handle.close()
        return None
    return handle


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
    instance_lock = _acquire_single_instance()
    if instance_lock is None:
        return
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
                Assistant(open_application, memory, OllamaAI(), MacOSComputerTools()),
                LocalWhisperListener(
                    duration=8,
                    on_recorded=lambda: AppHelper.callAfter(
                        self._recording_finished
                    ),
                ),
                MacOSSpeaker(),
            )
            self.status = rumps.MenuItem("Estado: listo")
            self.overlay = JarvisOverlay()
            self.overlay.hide()
            self.visual_session = False
            self._restart_claps_after_listening = False
            self.listen_item = rumps.MenuItem(
                "Escuchar (habla tras el sonido)  ⌃⌥Espacio",
                callback=self.start_listening,
            )
            self.clap_item = rumps.MenuItem(
                "Dos palmadas: activadas", callback=self.toggle_claps
            )
            login_title = (
                "Inicio automático: activado"
                if is_login_enabled()
                else "Inicio automático: desactivado"
            )
            self.login_item = rumps.MenuItem(
                login_title, callback=self.toggle_login
            )
            self.menu = [
                self.status,
                None,
                self.listen_item,
                self.clap_item,
                self.login_item,
                rumps.MenuItem("Salir de Jarvis", callback=self.quit_app),
            ]
            self.listening_lock = threading.Lock()
            self.hotkeys = keyboard.GlobalHotKeys(
                {"<ctrl>+<alt>+<space>": self.start_listening}
            )
            self.hotkeys.start()
            self.clap_detector = ClapDetector(
                lambda: AppHelper.callAfter(self.start_listening, "claps")
            )
            try:
                self.clap_detector.start()
            except Exception:
                self.clap_item.title = "Dos palmadas: no disponibles"

        def start_listening(self, _sender: Any = None) -> None:
            if not self.listening_lock.acquire(blocking=False):
                return
            self.visual_session = _sender == "claps"
            self._restart_claps_after_listening = (
                self.clap_detector.stream is not None
            )
            if self._restart_claps_after_listening:
                self.clap_detector.stop()
            AppHelper.callAfter(self._begin_visual_listening)
            threading.Thread(target=self._listen_worker, daemon=True).start()

        def _listen_worker(self) -> None:
            first_turn = True
            try:
                while True:
                    try:
                        command = self.service.listener.listen(
                            wait_timeout=None if first_turn else 10.0
                        )
                    except NoSpeechTimeout:
                        break
                    except SpeechError as error:
                        self.service.speaker.speak(str(error))
                        break

                    reply = self.service.assistant.handle(command)
                    AppHelper.callAfter(self._apply_status, "speaking")
                    self.service.speaker.speak(reply.message)
                    AppHelper.callAfter(
                        self._show_reply,
                        f"Tú: {command}\n\nJarvis: {reply.message}",
                    )
                    if reply.should_exit:
                        break
                    first_turn = False
                    AppHelper.callAfter(self._begin_followup_listening)
            except Exception as error:
                self.service.speaker.speak(f"Ha ocurrido un error: {error}")
            finally:
                AppHelper.callAfter(self._finish_listening)
                self.listening_lock.release()

        def _finish_listening(self) -> None:
            self._apply_status("ready")
            self.visual_session = False
            if self._restart_claps_after_listening:
                try:
                    self.clap_detector.start()
                    self.clap_detector.resume(cooldown=1.5)
                except Exception:
                    self.clap_item.title = "Dos palmadas: no disponibles"
            self._restart_claps_after_listening = False

        def _show_reply(self, message: str) -> None:
            rumps.notification("Jarvis", "Orden completada", message)

        def _begin_visual_listening(self) -> None:
            self._apply_status("listening")

        def _recording_finished(self) -> None:
            from AppKit import NSSound

            self._apply_status("processing")
            NSSound.beep()

        def _begin_followup_listening(self) -> None:
            self._apply_status("listening")

        def _apply_status(self, state: str) -> None:
            labels = {
                "ready": "Estado: listo",
                "listening": "Estado: escuchando…",
                "processing": "Estado: procesando…",
                "speaking": "Estado: hablando…",
            }
            self.status.title = labels[state]
            self.title = "◉" if state == "ready" else "●"
            if state == "ready":
                self.overlay.hide()
            elif self.visual_session:
                self.overlay.show(state)

        def toggle_claps(self, _sender: Any) -> None:
            if self.clap_detector.stream is None:
                try:
                    self.clap_detector.start()
                    self.clap_item.title = "Dos palmadas: activadas"
                except Exception:
                    self.clap_item.title = "Dos palmadas: no disponibles"
            else:
                self.clap_detector.stop()
                self.clap_item.title = "Dos palmadas: desactivadas"

        def toggle_login(self, _sender: Any) -> None:
            try:
                if is_login_enabled():
                    disable_login()
                    self.login_item.title = "Inicio automático: desactivado"
                else:
                    enable_login()
                    self.login_item.title = "Inicio automático: activado"
            except (OSError, RuntimeError) as error:
                rumps.alert("Jarvis", str(error))

        def quit_app(self, _sender: Any) -> None:
            self.hotkeys.stop()
            self.clap_detector.stop()
            self.overlay.hide()
            rumps.quit_application()

    JarvisMenuBar().run()


if __name__ == "__main__":
    main()
