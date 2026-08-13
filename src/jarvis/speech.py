from __future__ import annotations

import tempfile
import wave
from pathlib import Path
from typing import Any

from jarvis.audio import SpeechError


class LocalWhisperListener:
    """Graba una frase y la transcribe localmente con Whisper."""

    def __init__(
        self,
        model_name: str = "small",
        language: str = "es",
        duration: int = 6,
        sample_rate: int = 16_000,
    ) -> None:
        self.model_name = model_name
        self.language = language
        self.duration = duration
        self.sample_rate = sample_rate
        self._model: Any = None

    def listen(self) -> str:
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
        except ImportError as error:
            raise SpeechError(
                "Falta el módulo de voz. Instálalo con: pip install -e '.[voice]'"
            ) from error

        try:
            recording = sd.rec(
                int(self.duration * self.sample_rate),
                samplerate=self.sample_rate,
                channels=1,
                dtype="int16",
            )
            sd.wait()
        except Exception as error:
            raise SpeechError(
                "No puedo usar el micrófono. Revisa su permiso en Ajustes del Sistema."
            ) from error

        audio_path = Path(tempfile.gettempdir()) / "jarvis-last-command.wav"
        with wave.open(str(audio_path), "wb") as audio_file:
            audio_file.setnchannels(1)
            audio_file.setsampwidth(np.dtype("int16").itemsize)
            audio_file.setframerate(self.sample_rate)
            audio_file.writeframes(recording.tobytes())

        if self._model is None:
            self._model = WhisperModel(self.model_name, device="auto", compute_type="int8")

        segments, _ = self._model.transcribe(
            str(audio_path), language=self.language, vad_filter=True
        )
        transcript = " ".join(segment.text.strip() for segment in segments).strip()
        audio_path.unlink(missing_ok=True)
        if not transcript:
            raise SpeechError("No he entendido la frase. Inténtalo de nuevo.")
        return transcript
