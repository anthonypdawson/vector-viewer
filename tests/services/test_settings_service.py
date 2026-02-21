import json
from pathlib import Path

import pytest

from vector_inspector.services.settings_service import SettingsService


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
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
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
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    assert settings_file.exists()
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["last_connection"] == config


def test_set_get_and_clear(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()

    assert svc.get("theme", "light") == "light"
    svc.set("theme", "dark")
    assert svc.get("theme") == "dark"

    # Ensure persisted
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["theme"] == "dark"

    # Clear and verify
    svc.clear()
    assert svc.get("theme") is None

    # File should reflect cleared settings (no 'theme' key)
    data2 = json.loads(settings_file.read_text(encoding="utf-8"))
    assert "theme" not in data2


def test_missing_settings_file(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()
    # Remove file if exists
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    if settings_file.exists():
        settings_file.unlink()
    svc._load_settings()
    # Should not contain user keys, but may have defaults
    assert "theme" not in svc.settings or svc.settings["theme"] == "light"


def test_invalid_json_file(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    settings_file.parent.mkdir(parents=True, exist_ok=True)
    settings_file.write_text("{ invalid json }", encoding="utf-8")
    svc = SettingsService()
    # Should fallback to defaults, not user keys
    assert "theme" not in svc.settings or svc.settings["theme"] == "light"


def test_overwrite_key(temp_home):
    svc = SettingsService()
    svc.set("theme", "light")
    svc.set("theme", "dark")
    assert svc.get("theme") == "dark"


def test_unicode_and_large_value(temp_home):
    # Reset singleton for test isolation
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()
    unicode_val = "你好, мир, hello!"
    large_val = "x" * 10000
    svc.set("greeting", unicode_val)
    svc.set("blob", large_val)
    assert svc.get("greeting") == unicode_val
    assert svc.get("blob") == large_val
    # Validate persistence
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["greeting"] == unicode_val
    assert data["blob"] == large_val
