from __future__ import annotations

import subprocess
import importlib
import threading


class MacOSSpeaker:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._process: subprocess.Popen[bytes] | None = None

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
