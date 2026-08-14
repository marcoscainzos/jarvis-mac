from __future__ import annotations

import plistlib
import stat
import sys
from pathlib import Path


def install_app(applications_dir: Path | None = None) -> Path:
    applications = applications_dir or (Path.home() / "Applications")
    app = applications / "Jarvis.app"
    contents = app / "Contents"
    executable_dir = contents / "MacOS"
    executable_dir.mkdir(parents=True, exist_ok=True)

    jarvis_command = Path(sys.executable).parent / "jarvis-app"
    if not jarvis_command.exists():
        raise RuntimeError("No encuentro jarvis-app en el entorno activo.")

    plist = {
        "CFBundleDisplayName": "Jarvis",
        "CFBundleExecutable": "Jarvis",
        "CFBundleIdentifier": "dev.marcoscainzos.jarvis",
        "CFBundleName": "Jarvis",
        "CFBundlePackageType": "APPL",
        "CFBundleShortVersionString": "0.4.0",
        "LSUIElement": True,
        "NSHighResolutionCapable": True,
        "NSMicrophoneUsageDescription": "Jarvis necesita oír tus órdenes.",
    }
    with (contents / "Info.plist").open("wb") as handle:
        plistlib.dump(plist, handle)

    launcher = executable_dir / "Jarvis"
    launcher.write_text(
        "#!/bin/sh\nexec " + _shell_quote(str(jarvis_command)) + "\n",
        encoding="utf-8",
    )
    launcher.chmod(launcher.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP)
    return app


def _shell_quote(value: str) -> str:
    return "'" + value.replace("'", "'\\''") + "'"


def main() -> None:
    try:
        app = install_app()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"No se pudo instalar Jarvis.app: {error}") from error
    print(f"Jarvis instalado en {app}")


if __name__ == "__main__":
    main()
