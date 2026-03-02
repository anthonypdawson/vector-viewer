"""Tests for CLI entry-point argument parsing (--version, --help, telemetry)."""

from unittest.mock import patch

import pytest

from vector_inspector import get_version
from vector_inspector._cli import GITHUB_URL, _maybe_send_first_run_telemetry, parse_cli_args

# ---------------------------------------------------------------------------
# Output / exit-code tests (no subprocess needed; captured via capsys)
# ---------------------------------------------------------------------------


def test_version_flag_exits_zero_and_prints_version(capsys):
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit) as exc_info:
        parse_cli_args(["--version"])
    assert exc_info.value.code == 0
    assert get_version() in capsys.readouterr().out


def test_help_flag_exits_zero(capsys):
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit) as exc_info:
        parse_cli_args(["--help"])
    assert exc_info.value.code == 0


def test_help_lists_version_option(capsys):
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit):
        parse_cli_args(["--help"])
    assert "--version" in capsys.readouterr().out


def test_help_mentions_starting_app_without_args(capsys):
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit):
        parse_cli_args(["--help"])
    assert "without arguments" in capsys.readouterr().out


def test_help_epilog_contains_github_url(capsys):
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit):
        parse_cli_args(["--help"])
    assert GITHUB_URL in capsys.readouterr().out


def test_no_args_returns_without_exiting():
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"):
        parse_cli_args([])  # Must not raise


# ---------------------------------------------------------------------------
# Telemetry behaviour
# ---------------------------------------------------------------------------


class _FakeSettings:
    def __init__(self, first_run_done=False, telemetry_enabled=True):
        self._first_run_done = first_run_done
        self._telemetry_enabled = telemetry_enabled
        self.saved: dict = {}

    def get(self, key, default=None):
        if key == "cli.first_run_done":
            return self._first_run_done
        if key == "telemetry.enabled":
            return self._telemetry_enabled
        return default

    def set(self, key, value):
        self.saved[key] = value


class _FakeTelemetry:
    def __init__(self, settings_service=None):
        self.queued: list[dict] = []
        self._enabled = True

    def is_enabled(self):
        return self._enabled

    def queue_event(self, event):
        self.queued.append(event)

    def send_batch(self):
        pass


def test_first_run_telemetry_queued_when_enabled(monkeypatch):
    fake_settings = _FakeSettings(first_run_done=False, telemetry_enabled=True)
    fake_telemetry = _FakeTelemetry()

    monkeypatch.setattr(
        "vector_inspector.services.settings_service.SettingsService",
        lambda: fake_settings,
    )
    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.TelemetryService",
        lambda settings_service=None: fake_telemetry,
    )

    _maybe_send_first_run_telemetry("--version")

    assert len(fake_telemetry.queued) == 1
    assert fake_telemetry.queued[0]["event_name"] == "cli_first_use"
    assert fake_telemetry.queued[0]["metadata"]["command"] == "--version"
    assert fake_settings.saved.get("cli.first_run_done") is True


def test_first_run_telemetry_skipped_when_disabled(monkeypatch):
    fake_settings = _FakeSettings(first_run_done=False, telemetry_enabled=False)
    fake_telemetry = _FakeTelemetry()
    fake_telemetry._enabled = False

    monkeypatch.setattr(
        "vector_inspector.services.settings_service.SettingsService",
        lambda: fake_settings,
    )
    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.TelemetryService",
        lambda settings_service=None: fake_telemetry,
    )

    _maybe_send_first_run_telemetry("--help")

    assert fake_telemetry.queued == []


def test_first_run_telemetry_skipped_when_already_done(monkeypatch):
    fake_settings = _FakeSettings(first_run_done=True, telemetry_enabled=True)
    fake_telemetry = _FakeTelemetry()

    monkeypatch.setattr(
        "vector_inspector.services.settings_service.SettingsService",
        lambda: fake_settings,
    )
    monkeypatch.setattr(
        "vector_inspector.services.telemetry_service.TelemetryService",
        lambda settings_service=None: fake_telemetry,
    )

    _maybe_send_first_run_telemetry("--help")

    assert fake_telemetry.queued == []
