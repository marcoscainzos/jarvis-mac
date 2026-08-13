from __future__ import annotations

import subprocess


class MacOSSpeaker:
    def speak(self, message: str) -> None:
        subprocess.run(["say", "-v", "Mónica", message], check=False)
