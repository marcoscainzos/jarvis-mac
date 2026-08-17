from __future__ import annotations

import fcntl
import threading
from pathlib import Path
from typing import Any

from jarvis.app_service import JarvisService
from jarvis.assistant import Assistant
from jarvis.audio import NoSpeechTimeout, SpeechError, UnrecognizedSpeech
from jarvis.login_item import disable_login, enable_login, is_login_enabled
from jarvis.local_ai import OllamaAI
from jarvis.macos import MacOSComputerTools, open_application
from jarvis.macos_speech import MacOSSpeaker
from jarvis.memory import SQLiteMemory
from jarvis.research import BackgroundResearcher, ResearchResult
from jarvis.speech import LocalWhisperListener
from jarvis.task_engine import TaskEngine, TaskSnapshot
from jarvis.project_companion import ProjectCompanion, ProjectSession
from jarvis.screen_vision import ScreenVision
from jarvis.wake_word import WakeWordDetector, contains_sleep_word


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
            ai = OllamaAI(history_path=Path.home() / ".jarvis" / "conversation.db")
            self.ai = ai
            self.computer_tools = MacOSComputerTools()
            self.researcher = BackgroundResearcher(
                ai.summarize_research,
                on_complete=lambda result: AppHelper.callAfter(
                    self._research_complete, result
                ),
                storage_path=Path.home() / ".jarvis" / "latest-research.json",
                on_source=lambda title, url, index, total: AppHelper.callAfter(
                    self._research_source, title, url, index, total
                ),
            )
            self.task_engine = TaskEngine(
                self.researcher,
                self.computer_tools,
                Path.home() / ".jarvis" / "current-task.json",
                on_update=lambda task: AppHelper.callAfter(self._task_update, task),
            )
            self.project_companion = ProjectCompanion(
                ScreenVision(),
                Path.home() / ".jarvis" / "project-session.json",
                on_update=lambda session, event: AppHelper.callAfter(
                    self._project_update, session, event
                ),
            )
            self.service = JarvisService(
                Assistant(
                    open_application,
                    memory,
                    ai,
                    self.computer_tools,
                    self.researcher,
                    self.task_engine,
                    self.project_companion,
                ),
                LocalWhisperListener(
                    duration=8,
                    on_recorded=lambda: AppHelper.callAfter(
                        self._recording_finished
                    ),
                ),
                MacOSSpeaker(),
            )
            threading.Thread(
                target=self._warm_up_voice,
                daemon=True,
            ).start()
            self.status = rumps.MenuItem("Estado: listo")
            self.overlay = JarvisOverlay()
            self.overlay.hide()
            self.visual_session = False
            self._restart_wake_word_after_listening = False
            self._pending_wake_command = ""
            self._sleep_requested = threading.Event()
            self.sleeping = False
            self.listen_item = rumps.MenuItem(
                "Escuchar (habla tras el sonido)  ⌃⌥Espacio",
                callback=self.start_listening,
            )
            self.wake_item = rumps.MenuItem(
                'Activación por “Jarvis”: activada', callback=self.toggle_wake_word
            )
            login_title = (
                "Inicio automático: activado"
                if is_login_enabled()
                else "Inicio automático: desactivado"
            )
            self.login_item = rumps.MenuItem(
                login_title, callback=self.toggle_login
            )
            self.task_item = rumps.MenuItem("Tarea: ninguna")
            self.cancel_task_item = rumps.MenuItem("Cancelar tarea", callback=self.cancel_task)
            self.project_item = rumps.MenuItem("Contexto visual: desactivado")
            self.stop_project_item = rumps.MenuItem(
                "Activar contexto visual", callback=self.toggle_project_context
            )
            self.menu = [
                self.status,
                self.task_item,
                self.cancel_task_item,
                self.project_item,
                self.stop_project_item,
                None,
                self.listen_item,
                self.wake_item,
                self.login_item,
                rumps.MenuItem("Salir de Jarvis", callback=self.quit_app),
            ]
            self.listening_lock = threading.Lock()
            self.hotkeys = keyboard.GlobalHotKeys(
                {"<ctrl>+<alt>+<space>": self.start_listening}
            )
            self.hotkeys.start()
            self.wake_detector = WakeWordDetector(
                self.service.listener,
                lambda command: AppHelper.callAfter(
                    self._wake_word_detected, command
                ),
                on_sleep=lambda: AppHelper.callAfter(self._sleep_now),
            )
            try:
                self.wake_detector.start()
            except Exception:
                self.wake_item.title = 'Activación por “Jarvis”: no disponible'

        def _project_update(self, session: ProjectSession, event: str) -> None:
            self.project_item.title = (
                f"Contexto: activo — {session.observations} observaciones"
                if session.active else "Contexto: pausado"
            )
            if event == "issue" and session.issues:
                rumps.notification("Jarvis detectó un problema", session.project, session.issues[-1])

        def toggle_project_context(self, _sender: Any) -> None:
            if self.project_companion.status().active:
                self.project_companion.stop()
                self.stop_project_item.title = "Activar contexto visual"
                return
            session = self.project_companion.start_context()
            self._project_update(session, "started")
            self.stop_project_item.title = "Pausar contexto visual"

        def _task_update(self, task: TaskSnapshot) -> None:
            labels = {"running": "en curso", "done": "terminada", "error": "con error", "cancelled": "cancelada", "idle": "ninguna"}
            self.task_item.title = f"Tarea: {labels.get(task.state, task.state)} — {task.step[:55]}"
            if task.state == "done":
                rumps.notification("Jarvis", "Tarea terminada", f"Informe verificado: {task.output}")
            elif task.state == "error":
                rumps.notification("Jarvis", "Tarea detenida", task.error)

        def cancel_task(self, _sender: Any) -> None:
            if not self.task_engine.cancel():
                rumps.notification("Jarvis", "Sin tarea activa", "No hay nada que cancelar.")

        def _warm_up_voice(self) -> None:
            try:
                self.service.listener.warm_up()
            except Exception:
                # La escucha mostrará el error concreto si el usuario la activa.
                pass
            self.ai.warm_up()

        def _research_complete(self, result: ResearchResult) -> None:
            self.status.title = "Estado: listo"
            rumps.notification(
                "Jarvis",
                "Investigación terminada",
                f"He comparado {len(result.sources)} fuentes sobre {result.query}.",
            )
            self._announce_research(
                "Investigación terminada. Ya puedes preguntarme qué he encontrado."
            )

        def _research_source(
            self, title: str, url: str, index: int, total: int
        ) -> None:
            self.status.title = f"Investigando: fuente {index} de {total}"
            self.computer_tools.show_research_source(url, first=index == 1)
            rumps.notification(
                "Jarvis investiga",
                f"Fuente {index} de {total}",
                title[:180],
            )
            self._announce_research(f"Fuente {index} de {total}: {title[:80]}.")

        def _announce_research(self, message: str) -> None:
            if not hasattr(self, "listening_lock"):
                return
            if not self.listening_lock.acquire(blocking=False):
                return
            wake_was_active = self.wake_detector.running
            if wake_was_active:
                self.wake_detector.pause()

            def worker() -> None:
                try:
                    self.service.speaker.speak(message)
                finally:
                    AppHelper.callAfter(
                        self._finish_research_announcement, wake_was_active
                    )

            threading.Thread(target=worker, daemon=True).start()

        def _finish_research_announcement(self, restart_wake: bool) -> None:
            if restart_wake:
                self.wake_detector.resume()
            self.listening_lock.release()

        def _wake_word_detected(self, command: str) -> None:
            self.sleeping = False
            self._sleep_requested.clear()
            self._pending_wake_command = command
            self.start_listening("wake_word")

        def _sleep_now(self) -> None:
            self._sleep_requested.set()
            self.sleeping = True
            self._pending_wake_command = ""
            self.service.speaker.stop()
            self.overlay.hide()
            self._apply_status("sleeping")
            self.wake_detector.resume()

        def start_listening(self, _sender: Any = None) -> None:
            if not self.listening_lock.acquire(blocking=False):
                return
            self.visual_session = _sender == "wake_word"
            self._restart_wake_word_after_listening = self.wake_detector.running
            if self._restart_wake_word_after_listening:
                self.wake_detector.pause()
            AppHelper.callAfter(self._begin_visual_listening)
            threading.Thread(target=self._listen_worker, daemon=True).start()

        def _listen_worker(self) -> None:
            first_turn = True
            try:
                while True:
                    try:
                        if first_turn and self._pending_wake_command:
                            command = self._pending_wake_command
                            self._pending_wake_command = ""
                        else:
                            command = self.service.listener.listen(
                                wait_timeout=None if first_turn else 10.0
                            )
                    except NoSpeechTimeout:
                        break
                    except UnrecognizedSpeech as error:
                        AppHelper.callAfter(self._apply_status, "speaking")
                        self.service.speaker.speak(str(error))
                        AppHelper.callAfter(self._begin_followup_listening)
                        continue
                    except SpeechError as error:
                        self.service.speaker.speak(str(error))
                        break

                    if contains_sleep_word(command):
                        AppHelper.callAfter(self._sleep_now)
                        break
                    # Mientras piensa y habla, el microfono atiende solo «duerme».
                    self.wake_detector.listen_for_sleep()
                    reply = self.service.assistant.handle(command)
                    if self._sleep_requested.is_set():
                        break
                    AppHelper.callAfter(self._apply_status, "speaking")
                    self.service.speaker.speak(reply.message)
                    if self._sleep_requested.is_set():
                        break
                    AppHelper.callAfter(
                        self._show_reply,
                        f"Tú: {command}\n\nJarvis: {reply.message}",
                    )
                    if reply.should_exit:
                        break
                    first_turn = False
                    self.wake_detector.pause()
                    AppHelper.callAfter(self._begin_followup_listening)
            except Exception as error:
                self.service.speaker.speak(f"Ha ocurrido un error: {error}")
            finally:
                AppHelper.callAfter(self._finish_listening)
                self.listening_lock.release()

        def _finish_listening(self) -> None:
            self._apply_status("sleeping" if self.sleeping else "ready")
            self.visual_session = False
            if self._restart_wake_word_after_listening:
                self.wake_detector.resume()
            self._restart_wake_word_after_listening = False

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
                "sleeping": 'Estado: dormido — di “Jarvis”',
            }
            self.status.title = labels[state]
            self.title = "◉" if state in {"ready", "sleeping"} else "●"
            if state in {"ready", "sleeping"}:
                self.overlay.hide()
            elif self.visual_session:
                self.overlay.show(state)

        def toggle_wake_word(self, _sender: Any) -> None:
            if self.wake_detector.running:
                self.wake_detector.stop()
                self.wake_item.title = 'Activación por “Jarvis”: desactivada'
            else:
                self.wake_detector.start()
                self.wake_item.title = 'Activación por “Jarvis”: activada'

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
            self.wake_detector.stop()
            self.project_companion.stop()
            self.overlay.hide()
            rumps.quit_application()

    JarvisMenuBar().run()


if __name__ == "__main__":
    main()
