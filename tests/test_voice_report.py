import json
from pathlib import Path
from tempfile import TemporaryDirectory

from jarvis.voice_report import build_voice_report


def test_builds_private_local_html_report() -> None:
    with TemporaryDirectory() as directory:
        folder = Path(directory)
        source = folder / "results.json"
        source.write_text(json.dumps([{
            "file": "/private/iris.wav", "transcript": "Iris abre Safari",
            "latency_seconds": 1.25, "word_error_rate": 0.0,
            "expected_wake": True, "detected_wake": True, "passed": True,
        }]), encoding="utf-8")
        report = build_voice_report(source, folder / "report.html")
        content = report.read_text(encoding="utf-8")
        assert "Informe de voz" in content
        assert "1.25 s" in content
        assert "100.0%" in content
