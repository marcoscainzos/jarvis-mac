from __future__ import annotations

import subprocess
import importlib
import threading
import queue
import re
from collections.abc import Callable


class MacOSSpeaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None
        self._stream_queue: queue.Queue[str | None] | None = None
        self._stream_thread: threading.Thread | None = None
        self._stream_buffer = ""
        self._stream_cancelled = threading.Event()
        self._stream_had_content = False
        self._on_stream_start: Callable[[], None] | None = None

    def begin_stream(self, on_start: Callable[[], None] | None = None) -> None:
        self._stream_queue = queue.Queue()
        self._stream_buffer = ""
        self._stream_had_content = False
        self._stream_cancelled.clear()
        self._on_stream_start = on_start
        self._stream_thread = threading.Thread(target=self._stream_worker, daemon=True)
        self._stream_thread.start()

    def feed_stream_chunk(self, chunk: str) -> None:
        if self._stream_queue is None or self._stream_cancelled.is_set():
            return
        self._stream_buffer += chunk
        while True:
            match = re.match(r"^(.+?[.!?])(?:\s+|$)", self._stream_buffer, flags=re.DOTALL)
            if match is None:
                break
            sentence = " ".join(match.group(1).split())
            self._stream_buffer = self._stream_buffer[match.end():]
            if sentence:
                self._enqueue_sentence(sentence)

    def finish_stream(self) -> bool:
        if self._stream_queue is None:
            return False
        remaining = " ".join(self._stream_buffer.split())
        if remaining and not self._stream_cancelled.is_set():
            self._enqueue_sentence(remaining)
        self._stream_queue.put(None)
        if self._stream_thread is not None:
            self._stream_thread.join(timeout=120)
        had_content = self._stream_had_content
        self._stream_queue = None
        self._stream_thread = None
        self._stream_buffer = ""
        return had_content

    def _enqueue_sentence(self, sentence: str) -> None:
        if not self._stream_had_content:
            self._stream_had_content = True
            if self._on_stream_start is not None:
                self._on_stream_start()
        if self._stream_queue is not None:
            self._stream_queue.put(sentence)

    def _stream_worker(self) -> None:
        current_queue = self._stream_queue
        if current_queue is None:
            return
        while True:
            sentence = current_queue.get()
            if sentence is None:
                return
            if not self._stream_cancelled.is_set():
                self.speak(sentence)

    def speak(self, message: str) -> None:
        process = subprocess.Popen(
            ["say", "-v", "Reed (Español (España))", "-r", "170", message],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        with self._lock:
            self._process = process
        self._stop_on_loud_voice(process)
        process.wait()
        with self._lock:
            if self._process is process:
                self._process = None

    def stop(self) -> None:
        self._stream_cancelled.set()
        with self._lock:
            process = self._process
        if process is not None and process.poll() is None:
            process.terminate()

    @staticmethod
    def _stop_on_loud_voice(process: subprocess.Popen[bytes]) -> None:
        """Permite cortar la locución diciendo «calla» con voz clara y alta."""
        try:
            np = importlib.import_module("numpy")
            sd = importlib.import_module("sounddevice")
            with sd.InputStream(samplerate=16_000, channels=1, dtype="int16", blocksize=800) as stream:
                loud_blocks = 0
                while process.poll() is None:
                    block, _overflowed = stream.read(800)
                    peak = int(np.max(np.abs(block.astype("int32"))))
                    loud_blocks = loud_blocks + 1 if peak >= 10_000 else 0
                    if loud_blocks >= 3:
                        process.terminate()
                        return
        except Exception:
            # La voz sigue funcionando aunque el micrófono no permita interrupciones.
            return
