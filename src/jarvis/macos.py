from __future__ import annotations

import subprocess


ALLOWED_APPS = {
    "calculadora": "Calculator",
    "calculator": "Calculator",
    "calendario": "Calendar",
    "calendar": "Calendar",
    "notas": "Notes",
    "notes": "Notes",
    "safari": "Safari",
    "terminal": "Terminal",
}


def open_application(requested_name: str) -> bool:
    """Abre únicamente aplicaciones incluidas en la lista segura."""
    app_name = ALLOWED_APPS.get(requested_name.lower().strip())
    if app_name is None:
        return False

    result = subprocess.run(
        ["open", "-a", app_name],
        check=False,
        capture_output=True,
        text=True,
    )
    return result.returncode == 0

