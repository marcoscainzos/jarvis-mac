from pathlib import Path

import jarvis.login_item as login_item


def test_creates_login_launch_agent(tmp_path, monkeypatch) -> None:
    app = tmp_path / "Applications/Jarvis.app"
    app.mkdir(parents=True)
    target = tmp_path / "LaunchAgents/dev.marcoscainzos.jarvis.plist"
    monkeypatch.setattr(login_item, "launch_agent_path", lambda: target)

    assert login_item.enable_login(app) == target
    assert login_item.is_login_enabled()

    login_item.disable_login()
    assert not login_item.is_login_enabled()
