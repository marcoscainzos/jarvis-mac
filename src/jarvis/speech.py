from __future__ import annotations

import importlib
import sys
import tempfile
import traceback
import wave
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from jarvis.audio import SpeechError


class LocalWhisperListener:
    """Graba una frase y la transcribe localmente con Whisper."""

    def __init__(
        self,
        model_name: str = "small",
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

    def listen(self) -> str:
        np, sd, whisper_model = self._load_dependencies()

        try:
            recording = self._record_until_silence(np, sd)
        except Exception as error:
            sd.stop()
            raise SpeechError(
                "No puedo usar el micrófono. Revisa su permiso en Ajustes del Sistema."
            ) from error

        if self.on_recorded:
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
            if self._model is None:
                self._model = whisper_model(
                    self.model_name, device="auto", compute_type="int8"
                )
            segments, _ = self._model.transcribe(
                str(audio_path), language=self.language, vad_filter=True
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
            raise SpeechError("No he entendido la frase. Inténtalo de nuevo.")
        return transcript

    def _record_until_silence(self, np: Any, sd: Any) -> Any:
        """Termina poco después de que el usuario deja de hablar."""
        block_seconds = 0.10
        block_frames = int(self.sample_rate * block_seconds)
        max_speech_blocks = max(1, int(self.duration / block_seconds))
        silence_blocks_needed = int(0.7 / block_seconds)
        calibration_blocks = 3
        calibration_levels: list[float] = []
        noise_floor = 80.0
        speech_started = False
        silent_blocks = 0
        pre_roll: deque[Any] = deque(maxlen=5)
        chunks: list[Any] = []
        speech_blocks = 0

        with sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
                blocksize=block_frames,
            ) as stream:
            index = 0
            while True:
                block, _overflowed = stream.read(block_frames)
                samples = block.astype("float32")
                rms = float(np.sqrt(np.mean(samples * samples)))
                if index < calibration_blocks:
                    calibration_levels.append(rms)
                    pre_roll.append(block.copy())
                    if index == calibration_blocks - 1:
                        noise_floor = float(np.median(calibration_levels))
                    index += 1
                    continue

                threshold = noise_floor + max(140.0, noise_floor * 1.20)
                if rms >= threshold:
                    if not speech_started:
                        chunks.extend(pre_roll)
                    speech_started = True
                    chunks.append(block.copy())
                    speech_blocks += 1
                    silent_blocks = 0
                else:
                    if not speech_started:
                        noise_floor = noise_floor * 0.80 + rms * 0.20
                        pre_roll.append(block.copy())
                    else:
                        chunks.append(block.copy())
                        speech_blocks += 1
                        silent_blocks += 1
                if speech_started and (
                    silent_blocks >= silence_blocks_needed
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
