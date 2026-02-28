"""Tests for LoadingScreen and show_loading_screen."""

import sys
import types

from vector_inspector.ui.loading_screen import LoadingScreen, show_loading_screen

# ---------------------------------------------------------------------------
# LoadingScreen widget tests
# ---------------------------------------------------------------------------


def test_loading_screen_instantiates(qtbot):
    screen = LoadingScreen(
        logo_path="/nonexistent/logo.png",  # triggers skip-logo branch
        version="v1.0.0",
        app_name="Test App",
        tagline="A tagline",
        loading_text="Loading…",
    )
    qtbot.addWidget(screen)
    assert screen is not None


def test_loading_screen_loading_label_text(qtbot):
    screen = LoadingScreen(
        logo_path="/nonexistent/logo.png",
        version="v1.0.0",
        app_name="Test App",
        tagline="A tagline",
        loading_text="Please wait",
    )
    qtbot.addWidget(screen)
    assert screen.loading_label.text() == "Please wait"


def test_loading_screen_set_loading_text(qtbot):
    screen = LoadingScreen(
        logo_path="/nonexistent/logo.png",
        version="v1.0.0",
        app_name="Test App",
        tagline="A tagline",
        loading_text="Initial",
    )
    qtbot.addWidget(screen)
    screen.set_loading_text("Updated message")
    assert screen.loading_label.text() == "Updated message"


def test_loading_screen_skip_checkbox_exists(qtbot):
    screen = LoadingScreen(
        logo_path="/nonexistent/logo.png",
        version="v0.9.0",
        app_name="Vector Inspector",
        tagline="Explore your vectors",
        loading_text="Init…",
    )
    qtbot.addWidget(screen)
    assert hasattr(screen, "skip_loading_checkbox")


def test_loading_screen_skip_checkbox_triggers_settings(qtbot, monkeypatch):
    """_on_skip_changed should call settings.set without error."""
    saved = {}

    class FakeSettings:
        def set(self, key, value):
            saved[key] = value

    # Patch SettingsService where it is imported inside the method
    fake_mod = types.ModuleType("vector_inspector.services.settings_service")
    fake_mod.SettingsService = lambda: FakeSettings()
    monkeypatch.setitem(sys.modules, "vector_inspector.services.settings_service", fake_mod)

    screen = LoadingScreen(
        logo_path="/nonexistent/logo.png",
        version="v1.0.0",
        app_name="Test App",
        tagline="Tagline",
        loading_text="Loading",
    )
    qtbot.addWidget(screen)
    screen.skip_loading_checkbox.setChecked(True)
    assert "hide_loading_screen" in saved


# ---------------------------------------------------------------------------
# show_loading_screen function tests
# ---------------------------------------------------------------------------


def test_show_loading_screen_returns_none_when_disabled(monkeypatch):
    """Returns None when hide_loading_screen setting is True."""

    class FakeSettings:
        def get(self, key, default=None):
            if key == "hide_loading_screen":
                return True
            return default

    fake_mod = types.ModuleType("vector_inspector.services.settings_service")
    fake_mod.SettingsService = lambda: FakeSettings()
    monkeypatch.setitem(sys.modules, "vector_inspector.services.settings_service", fake_mod)

    result = show_loading_screen(
        app_name="Test",
        version="v1.0.0",
        tagline="Tag",
    )
    assert result is None


def test_show_loading_screen_returns_loading_screen_when_enabled(qtbot, monkeypatch):
    """Returns a LoadingScreen instance when setting is enabled."""

    class FakeSettings:
        def get(self, key, default=None):
            if key == "hide_loading_screen":
                return False
            return default

        def set(self, key, value):
            pass

    fake_mod = types.ModuleType("vector_inspector.services.settings_service")
    fake_mod.SettingsService = lambda: FakeSettings()
    monkeypatch.setitem(sys.modules, "vector_inspector.services.settings_service", fake_mod)

    result = show_loading_screen(
        app_name="Vector Inspector",
        version="v1.0.0",
        tagline="Explore your vectors",
        logo_path="/nonexistent/logo.png",
    )
    assert result is not None
    assert isinstance(result, LoadingScreen)
    qtbot.addWidget(result)
    result.close()
