import logging
import os

# Ensure headless Qt platform as early as possible to avoid GUI initialization
# before tests or imported modules can touch Qt.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

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

        # Patch TelemetryService methods to no-ops to guarantee no network activity
        def _noop_queue_event(self, event):
            return None

        def _noop_send_batch(self):
            return None

        def _noop_send_launch_ping(self, *args, **kwargs):
            return None

        def _noop_send_error_event(self, *args, **kwargs):
            return None

        TelemetryService.queue_event = _noop_queue_event
        TelemetryService.send_batch = _noop_send_batch
        TelemetryService.send_launch_ping = _noop_send_launch_ping
        TelemetryService.send_error_event = _noop_send_error_event
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

    return FakeSettings()
