from jarvis.memory import SQLiteMemory


def test_sqlite_memory_persists_between_instances(tmp_path) -> None:
    path = tmp_path / "memory.db"
    first = SQLiteMemory(path)
    first.set("user_name", "Marcos")

    second = SQLiteMemory(path)
    assert second.get("user_name") == "Marcos"

    second.forget("user_name")
    assert first.get("user_name") is None
