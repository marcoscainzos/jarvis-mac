from __future__ import annotations

import subprocess


class MacOSSpeaker:
    def speak(self, message: str) -> None:
        subprocess.run(
            ["say", "-v", "Reed (Español (España))", "-r", "172", message],
            check=False,
        )
