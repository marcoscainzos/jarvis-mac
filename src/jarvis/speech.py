from __future__ import annotations

import importlib
import sys
import tempfile
import threading
import traceback
import wave
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from jarvis.audio import NoSpeechTimeout, SpeechError, UnrecognizedSpeech


class LocalWhisperListener:
    """Graba una frase y la transcribe localmente con Whisper."""

    def __init__(
        self,
        model_name: str = "base",
        language: str = "es",
        duration: int = 6,
        sample_rate: int = 16_000,
        on_recorded: Callable[[], None] | None = None,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.duration = duration
        self.sample_rate = sample_rate
        self.on_recorded = on_recorded
        self._model: Any = None
        self._model_lock = threading.Lock()
        self._cancel_recording = threading.Event()

    def cancel_recording(self) -> None:
        """Interrumpe de forma segura una espera de micrófono en curso."""
        self._cancel_recording.set()

    def warm_up(self) -> None:
        """Carga Whisper en segundo plano para acelerar la primera orden."""
        _np, _sd, whisper_model = self._load_dependencies()
        self._ensure_model(whisper_model)

    def listen(
        self,
        wait_timeout: float | None = None,
        notify_recorded: bool = True,
        wake_mode: bool = False,
    ) -> str:
        np, sd, whisper_model = self._load_dependencies()
        self._cancel_recording.clear()

        try:
            recording = self._record_until_silence(
                np, sd, wait_timeout, wake_mode=wake_mode
            )
        except NoSpeechTimeout:
            raise
        except Exception as error:
            sd.stop()
            raise SpeechError(
                "No puedo usar el micrófono. Revisa su permiso en Ajustes del Sistema."
            ) from error

        if notify_recorded and self.on_recorded:
            self.on_recorded()

        peak = int(np.max(np.abs(recording.astype("int32"))))
        if peak < 80:
            raise SpeechError(
                "No está entrando sonido por el micrófono. Revisa el permiso de Jarvis."
            )

        temporary = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        audio_path = Path(temporary.name)
        temporary.close()
        with wave.open(str(audio_path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(np.dtype("int16").itemsize)
            audio_file.setframerate(self.sample_rate)
            audio_file.writeframes(recording.tobytes())

        try:
            self._ensure_model(whisper_model)
            transcription_options: dict[str, Any] = {
                "language": self.language,
                "vad_filter": not wake_mode,
                "beam_size": 1,
                "best_of": 1,
                "condition_on_previous_text": False,
            }
            if wake_mode:
                # Una sola palabra puede ser eliminada por VAD; este contexto
                # ayuda a Whisper a conservar y escribir correctamente Jarvis.
                transcription_options["initial_prompt"] = "Jarvis"
            else:
                transcription_options["vad_parameters"] = {
                    "min_silence_duration_ms": 300
                }
            segments, _ = self._model.transcribe(
                str(audio_path), **transcription_options
            )
            transcript = " ".join(
                segment.text.strip() for segment in segments
            ).strip()
        except Exception as error:
            raise SpeechError(
                "No se pudo cargar o ejecutar el modelo de voz. "
                "Comprueba la conexión durante la primera descarga."
            ) from error
        finally:
            audio_path.unlink(missing_ok=True)
        if not transcript:
            raise UnrecognizedSpeech("No he entendido esa frase. Sigo escuchando.")
        return transcript

    def _ensure_model(self, whisper_model: Any) -> None:
        if self._model is not None:
            return
        with self._model_lock:
            if self._model is None:
                self._model = whisper_model(
                    self.model_name, device="auto", compute_type="int8"
                )

    def _record_until_silence(
        self,
        np: Any,
        sd: Any,
        wait_timeout: float | None = None,
        wake_mode: bool = False,
    ) -> Any:
        """Termina poco después de que el usuario deja de hablar."""
        block_seconds = 0.05
        block_frames = int(self.sample_rate * block_seconds)
        maximum_duration = 2.5 if wake_mode else self.duration
        max_speech_blocks = max(1, int(maximum_duration / block_seconds))
        silence_blocks_needed = int((0.35 if wake_mode else 0.80) / block_seconds)
        minimum_voiced_blocks = int((0.15 if wake_mode else 0.50) / block_seconds)
        noise_floor = 30.0
        speech_started = False
        silent_blocks = 0
        pre_roll: deque[Any] = deque(maxlen=5)
        chunks: list[Any] = []
        speech_blocks = 0
        voiced_blocks = 0
        waiting_blocks = 0

        with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
            index = 0
            while True:
                if self._cancel_recording.is_set():
                    raise NoSpeechTimeout()
                block, _overflowed = stream.read(block_frames)
                samples = block.astype("float32")
                rms = float(np.sqrt(np.mean(samples * samples)))
                threshold = noise_floor + max(90.0, noise_floor * 1.50)
                if rms >= threshold:
                    if not speech_started:
                        chunks.extend(pre_roll)
                    speech_started = True
                    chunks.append(block.copy())
                    speech_blocks += 1
                    voiced_blocks += 1
                    silent_blocks = 0
                else:
                    if not speech_started:
                        noise_floor = noise_floor * 0.80 + rms * 0.20
                        pre_roll.append(block.copy())
                        waiting_blocks += 1
                        if (
                            wait_timeout is not None
                            and waiting_blocks * block_seconds >= wait_timeout
                        ):
                            raise NoSpeechTimeout()
                    else:
                        chunks.append(block.copy())
                        speech_blocks += 1
                        silent_blocks += 1
                if speech_started and (
                    (
                        voiced_blocks >= minimum_voiced_blocks
                        and silent_blocks >= silence_blocks_needed
                    )
                    or speech_blocks >= max_speech_blocks
                ):
                    break
                index += 1
        return np.concatenate(chunks, axis=0)

    @staticmethod
    def _load_dependencies() -> tuple[Any, Any, Any]:
        loaded: dict[str, Any] = {}
        for module_name in ("numpy", "sounddevice", "faster_whisper"):
            try:
                loaded[module_name] = importlib.import_module(module_name)
            except Exception as error:
                LocalWhisperListener._write_diagnostic(module_name, error)
                raise SpeechError(
                    f"No puedo cargar {module_name}: {error}. "
                    "Se ha guardado el diagnóstico en ~/.jarvis/jarvis.log"
                ) from error
        return (
            loaded["numpy"],
            loaded["sounddevice"],
            loaded["faster_whisper"].WhisperModel,
        )

    @staticmethod
    def _write_diagnostic(module_name: str, error: Exception) -> None:
        log_path = Path.home() / ".jarvis" / "jarvis.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        details = (
            f"\n[{datetime.now().isoformat(timespec='seconds')}] "
            f"voice import failed: {module_name}\n"
            f"Python: {sys.executable}\n"
            f"{''.join(traceback.format_exception(error))}"
        )
        with log_path.open("a", encoding="utf-8") as log_file:
            log_file.write(details)
