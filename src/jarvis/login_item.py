from __future__ import annotations

import plistlib
from pathlib import Path


LABEL = "dev.marcoscainzos.iris"


def launch_agent_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def enable_login(app_path: Path | None = None) -> Path:
    application = app_path or (Path.home() / "Applications" / "Iris.app")
    if not application.exists():
        raise RuntimeError(f"No encuentro Iris.app en {application}")
    target = launch_agent_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    configuration = {
        "Label": LABEL,
        "ProgramArguments": ["/usr/bin/open", str(application)],
        "RunAtLoad": True,
    }
    with target.open("wb") as handle:
        plistlib.dump(configuration, handle)
    return target


def disable_login() -> None:
    launch_agent_path().unlink(missing_ok=True)


def is_login_enabled() -> bool:
    return launch_agent_path().exists()


def main() -> None:
    try:
        path = enable_login()
    except (OSError, RuntimeError) as error:
        raise SystemExit(f"No se pudo activar el inicio automático: {error}") from error
    print(f"Inicio automático activado en {path}")
