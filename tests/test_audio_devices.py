from jarvis.audio_devices import select_input_device


def test_prefers_default_physical_microphone() -> None:
    devices = [
        {"name": "BlackHole 2ch", "max_input_channels": 2},
        {"name": "Micrófono del MacBook Pro", "max_input_channels": 1},
        {"name": "AirPods", "max_input_channels": 1},
    ]
    assert select_input_device(devices, default_index=2) == 2


def test_ignores_virtual_and_output_only_devices() -> None:
    devices = [
        {"name": "BlackHole 2ch", "max_input_channels": 2},
        {"name": "Altavoces", "max_input_channels": 0},
        {"name": "MacBook Microphone", "max_input_channels": 1},
    ]
    assert select_input_device(devices, default_index=0) == 2


def test_returns_none_when_no_microphone_exists() -> None:
    assert select_input_device([{"name": "Salida", "max_input_channels": 0}]) is None
