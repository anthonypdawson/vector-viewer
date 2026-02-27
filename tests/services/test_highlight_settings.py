import json
from pathlib import Path

import pytest

from vector_inspector.services.settings_service import SettingsService


@pytest.fixture()
def temp_home(tmp_path):
    original_home = Path.home
    Path.home = lambda: tmp_path  # type: ignore
    try:
        yield tmp_path
    finally:
        Path.home = original_home


def test_highlight_color_roundtrip(temp_home):
    SettingsService._instance = None
    SettingsService._initialized = False
    svc = SettingsService()

    # Defaults come from ui.styles if not set
    default = svc.get_highlight_color()
    assert default.startswith("rgba(")

    # Set and persist
    svc.set_highlight_color("rgba(10,20,30,1)")
    svc.set_highlight_color_bg("rgba(10,20,30,0.1)")

    # Create a new instance to ensure values read from disk
    svc2 = SettingsService()
    assert svc2.get_highlight_color() == "rgba(10,20,30,1)"
    assert svc2.get_highlight_color_bg() == "rgba(10,20,30,0.1)"

    # Verify file contents
    settings_file = temp_home / ".vector-inspector" / "settings.json"
    data = json.loads(settings_file.read_text(encoding="utf-8"))
    assert data["ui.highlight_color"] == "rgba(10,20,30,1)"
    assert data["ui.highlight_color_bg"] == "rgba(10,20,30,0.1)"
