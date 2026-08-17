from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import re
import sys
import time
import unicodedata

from jarvis.speech import LocalWhisperListener
from jarvis.wake_word import command_after_wake_word


def normalize_words(text: str) -> list[str]:
    value = unicodedata.normalize("NFKD", text.casefold())
    value = "".join(char for char in value if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", value)


def word_error_rate(expected: str, actual: str) -> float:
    reference = normalize_words(expected)
    hypothesis = normalize_words(actual)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    previous = list(range(len(hypothesis) + 1))
    for index, expected_word in enumerate(reference, start=1):
        current = [index]
        for other_index, actual_word in enumerate(hypothesis, start=1):
            current.append(min(
                current[-1] + 1,
                previous[other_index] + 1,
                previous[other_index - 1] + (expected_word != actual_word),
            ))
        previous = current
    return previous[-1] / len(reference)


@dataclass(frozen=True)
class VoiceBenchmarkResult:
    file: str
    expected: str
    transcript: str
    latency_seconds: float
    word_error_rate: float
    expected_wake: bool
    detected_wake: bool
    passed: bool


def run_manifest(manifest_path: Path, model: str = "base") -> list[VoiceBenchmarkResult]:
    samples = json.loads(manifest_path.read_text(encoding="utf-8"))
    listener = LocalWhisperListener(model_name=model)
    listener.warm_up()
    results: list[VoiceBenchmarkResult] = []
    for sample in samples:
        audio_path = Path(sample["file"]).expanduser()
        started = time.perf_counter()
        transcript = listener.transcribe_file(audio_path)
        latency = time.perf_counter() - started
        expected = str(sample.get("expected", ""))
        expected_wake = bool(sample.get("wake", False))
        detected_wake = command_after_wake_word(transcript) is not None
        error_rate = word_error_rate(expected, transcript) if expected else 0.0
        passed = detected_wake == expected_wake and (not expected or error_rate <= 0.25)
        results.append(VoiceBenchmarkResult(
            str(audio_path), expected, transcript, round(latency, 3),
            round(error_rate, 4), expected_wake, detected_wake, passed,
        ))
    return results


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Uso: iris-voice-benchmark manifest.json [modelo]")
    results = run_manifest(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "base")
    print(json.dumps([asdict(result) for result in results], ensure_ascii=False, indent=2))
    if not all(result.passed for result in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
