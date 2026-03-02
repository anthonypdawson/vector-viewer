"""Tests for CLI entry-point argument parsing (--version, --help, telemetry)."""

import os
from unittest.mock import patch

import pytest

from vector_inspector import get_version
from vector_inspector._cli import GITHUB_URL, _handle_dump_settings, _maybe_send_first_run_telemetry, parse_cli_args

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


# ---------------------------------------------------------------------------
# Runtime-only flag → env var mapping
# ---------------------------------------------------------------------------


def test_no_telemetry_flag_sets_env_var(monkeypatch):
    monkeypatch.delenv("VI_NO_TELEMETRY", raising=False)
    parse_cli_args(["--no-telemetry"])
    assert os.environ.get("VI_NO_TELEMETRY") == "1"


def test_no_telemetry_prevents_first_run_event(monkeypatch):
    monkeypatch.setenv("VI_NO_TELEMETRY", "1")
    # Returns immediately without importing services; must not raise.
    _maybe_send_first_run_telemetry("--version")


def test_no_telemetry_skips_event_when_env_set(monkeypatch):
    monkeypatch.setenv("VI_NO_TELEMETRY", "1")
    # Patch the lazy import path; if VI_NO_TELEMETRY guard doesn't fire first,
    # the import would raise — proving the env var short-circuits correctly.
    with patch(
        "vector_inspector.services.settings_service.SettingsService", side_effect=AssertionError("should not be called")
    ):
        _maybe_send_first_run_telemetry("--help")  # must not raise


def test_log_level_flag_sets_env_var(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    parse_cli_args(["--log-level", "debug"])
    assert os.environ.get("LOG_LEVEL") == "DEBUG"


def test_log_level_flag_case_insensitive(monkeypatch):
    monkeypatch.delenv("LOG_LEVEL", raising=False)
    parse_cli_args(["--log-level", "INFO"])
    assert os.environ.get("LOG_LEVEL") == "INFO"


def test_no_splash_flag_sets_env_var(monkeypatch):
    monkeypatch.delenv("VI_NO_SPLASH", raising=False)
    parse_cli_args(["--no-splash"])
    assert os.environ.get("VI_NO_SPLASH") == "1"


def test_config_flag_sets_env_var(monkeypatch, tmp_path):
    cfg = str(tmp_path / "custom.json")
    monkeypatch.delenv("VI_CONFIG_PATH", raising=False)
    parse_cli_args(["--config", cfg])
    assert os.environ.get("VI_CONFIG_PATH") == cfg


# ---------------------------------------------------------------------------
# --dump-settings
# ---------------------------------------------------------------------------


def test_dump_settings_prints_json_and_exits_zero(tmp_path, capsys):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"foo": "bar"}', encoding="utf-8")
    with pytest.raises(SystemExit) as exc_info:
        _handle_dump_settings(str(settings_file))
    assert exc_info.value.code == 0
    assert '"foo"' in capsys.readouterr().out


def test_dump_settings_empty_dict_when_file_missing(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc_info:
        _handle_dump_settings(str(tmp_path / "nonexistent.json"))
    assert exc_info.value.code == 0
    assert capsys.readouterr().out.strip() == "{}"


def test_dump_settings_via_parse_cli_args(tmp_path, capsys):
    settings_file = tmp_path / "settings.json"
    settings_file.write_text('{"key": "value"}', encoding="utf-8")
    with patch("vector_inspector._cli._maybe_send_first_run_telemetry"), pytest.raises(SystemExit) as exc_info:
        parse_cli_args(["--dump-settings", "--config", str(settings_file)])
    assert exc_info.value.code == 0
    assert '"key"' in capsys.readouterr().out
