import json
from pathlib import Path

import pytest

from vector_viewer.services.settings_service import SettingsService


@pytest.fixture()
def temp_home(tmp_path):
    # Monkeypatch Path.home() to point to a temporary directory for isolation
    original_home = Path.home
    Path.home = lambda: tmp_path  # type: ignore
    try:
        yield tmp_path
    finally:
        Path.home = original_home  # restore


def test_last_connection_roundtrip(temp_home):
    svc = SettingsService()
    assert svc.get_last_connection() is None

    config = {
        "provider": "chromadb",
        "connection_type": "persistent",
        "path": "./data/chroma_db",
    }
    svc.save_last_connection(config)

    # Create a new service to ensure it reads from disk
    svc2 = SettingsService()
    assert svc2.get_last_connection() == config

    # Validate file exists with expected content
    settings_file = temp_home / ".vector-viewer" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["last_connection"] == config


def test_set_get_and_clear(temp_home):
    svc = SettingsService()

    assert svc.get("theme", "light") == "light"
    svc.set("theme", "dark")
    assert svc.get("theme") == "dark"

    # Ensure persisted
    settings_file = temp_home / ".vector-viewer" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"

    # Clear and verify
    svc.clear()
    assert svc.get("theme") is None

    # File should reflect cleared settings
    data2 = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data2 == {}
