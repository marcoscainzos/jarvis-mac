from pathlib import Path

import jarvis.macos_installer as installer


def test_installer_creates_application_bundle(tmp_path, monkeypatch) -> None:
    fake_python = tmp_path / "venv/bin/python"
    fake_command = fake_python.parent / "jarvis-app"
    fake_command.parent.mkdir(parents=True)
    fake_command.touch()
    monkeypatch.setattr(installer.sys, "executable", str(fake_python))

    app = installer.install_app(tmp_path / "Applications")

    assert (app / "Contents/Info.plist").exists()
    launcher = app / "Contents/MacOS/Jarvis"
    assert launcher.exists()
    assert str(fake_command) in launcher.read_text()
    assert "/usr/bin/arch -arm64" in launcher.read_text()
