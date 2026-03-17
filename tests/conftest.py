import logging
import os

# Ensure headless Qt platform as early as possible to avoid GUI initialization
# before tests or imported modules can touch Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Do NOT force-disable telemetry here — tests explicitly verify telemetry
# behaviour and will set `VI_NO_TELEMETRY` themselves where needed.

import pytest

from tests.fakes.fake_provider import FakeProvider
from vector_inspector.services import ThreadedTaskRunner
from vector_inspector.state import AppState


def pytest_configure(config):
    """Global test configuration: disable telemetry and patch telemetry methods.

    This ensures unit tests never send telemetry or perform network I/O.
    Pytest configuration for headless Qt testing.

    This method ensures Qt uses the offscreen platform during test runs so
    tests do not create visible windows locally.
    """
    try:
        # Delay imports so test environment can control import order
        from vector_inspector.services.settings_service import SettingsService
        from vector_inspector.services.telemetry_service import TelemetryService

        # Ensure the persistent settings flag is off
        try:
            SettingsService().set("telemetry.enabled", False)
        except Exception:
            # Best-effort: tests should not fail if settings backend isn't available
            logging.debug("Failed to set telemetry.enabled in SettingsService")

        # Reset the singleton so each test session starts clean. Tests that
        # need to assert telemetry behavior will explicitly enable it and
        # monkeypatch network calls. Do not replace TelemetryService methods
        # here so the service can be exercised by unit tests.
        TelemetryService.reset_for_tests()
    except Exception as _err:
        # Fail-safe: do not prevent pytest from running if telemetry internals change
        logging.debug(f"Could not patch telemetry for tests: {_err}")


@pytest.fixture
def fake_provider():
    """Provide a fresh FakeProvider instance for tests."""
    provider = FakeProvider()
    # Populate with a default collection for convenience
    provider.create_collection(
        "test_collection",
        ["doc1", "doc2", "doc3"],  # docs (positional)
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],  # metadatas
        [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],  # embeddings
    )
    return provider


# Add a second fixture for an *empty* provider
# Useful for tests that need to assert "no collections" or "create first collection".


@pytest.fixture
def empty_fake_provider():
    return FakeProvider()


# Add a fixture that returns both provider + preloaded collection name
# This reduces magic strings in tests and keeps things DRY.


@pytest.fixture
def fake_provider_with_name():
    provider = FakeProvider()
    name = "test_collection"
    provider.create_collection(
        name,
        ["doc1", "doc2", "doc3"],  # docs (positional)
        [{"name": "a"}, {"name": "b"}, {"name": "c"}],  # metadatas
        [[1.0, 0.0], [0.0, 1.0], [0.5, 0.5]],  # embeddings
    )
    return provider, name


@pytest.fixture
def app_state_with_fake_provider(fake_provider):
    """Provide an AppState instance with a FakeProvider connection."""
    app_state = AppState()
    app_state.provider = fake_provider
    return app_state


@pytest.fixture
def task_runner():
    """Provide a ThreadedTaskRunner instance for tests."""
    return ThreadedTaskRunner()


@pytest.fixture
def fake_settings():
    """Fake SettingsService that suppresses the splash dialog."""

    class FakeSettings:
        def get(self, key, default=None):
            if key == "hide_splash_window":
                return True
            return default

        # Provide accent enable/disable API used by SettingsDialog and other UI
        def get_use_accent_enabled(self) -> bool:
            # Default to False for tests unless explicitly set
            return bool(getattr(self, "_use_accent", False))

        def set_use_accent_enabled(self, enabled: bool):
            # Store the flag for inspection in tests
            self._use_accent = bool(enabled)

    return FakeSettings()


@pytest.fixture
def webengine_cleanup(qtbot):
    """Opt-in fixture to track widgets added via `qtbot.addWidget` and detach
    their `QWebEngineView` pages on teardown to avoid Qt WebEngineProfile
    warnings. Use in tests that create `QWebEngineView` widgets (e.g.
    `PlotPanel`, `HistogramPanel`) by accepting the `webengine_cleanup` fixture.

    Example:
        def test_something(qtbot, webengine_cleanup):
            panel = PlotPanel()
            qtbot.addWidget(panel)

    Widgets that are not added via ``qtbot.addWidget`` can be tracked manually
    by appending them to the ``webengine_cleanup`` list.
    """
    created = []
    orig_add = qtbot.addWidget

    def _add_widget(widget):
        created.append(widget)
        return orig_add(widget)

    qtbot.addWidget = _add_widget
    try:
        yield created
    finally:
        # Teardown: detach WebEngine pages from tracked widgets. Do not close or
        # delete the widget itself; pytest-qt will handle widget closing.
        for w in created:
            try:
                if hasattr(w, "web_view"):
                    try:
                        p = None
                        try:
                            p = w.web_view.page()
                        except Exception:
                            p = None

                        if p is not None:
                            try:
                                p.setWebChannel(None)
                            except Exception:
                                pass
                            try:
                                p.setParent(None)
                            except Exception:
                                pass
                            try:
                                p.deleteLater()
                            except Exception:
                                pass

                        try:
                            w.web_view.setPage(None)
                        except Exception:
                            pass
                    except Exception:
                        pass
            except Exception:
                pass

    # Encourage Python to collect Qt wrappers and give Qt a moment to tear down
    try:
        import gc

        gc.collect()
    except Exception:
        pass
    try:
        qtbot.wait(50)
    except Exception:
        pass
