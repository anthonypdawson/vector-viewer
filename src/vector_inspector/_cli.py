"""Lightweight CLI argument parsing for Vector Inspector.

Handles --version, --help, and runtime-only flags before any Qt/GUI modules
are imported.  Runtime flags are propagated via environment variables so that
main.py and lower-level modules pick them up without any signature change.

Environment variables set (never persisted to disk):
  VI_NO_TELEMETRY=1   — disables telemetry for this process
  VI_NO_SPLASH=1      — skips the loading splash screen
  VI_CONFIG_PATH=PATH — alternate settings file path for this run
  LOG_LEVEL=LEVEL     — logging level (read by core/logging.py at import time)
"""

import argparse
import json
import os
import platform
import sys
from datetime import UTC, datetime
from pathlib import Path

from vector_inspector import get_version

GITHUB_URL = "https://github.com/anthonypdawson/vector-inspector"
_FIRST_RUN_KEY = "cli.first_run_done"
_LOG_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vector-inspector",
        description=(
            "Vector Inspector — a desktop GUI for visualizing and managing vector databases.\n"
            "\n"
            "Running 'vector-inspector' or 'python -m vector_inspector' without arguments\n"
            "starts the GUI application."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"For problems, visit: {GITHUB_URL}",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.add_argument(
        "--no-telemetry",
        action="store_true",
        help="Disable telemetry for this run only (does not change saved settings).",
    )
    parser.add_argument(
        "--log-level",
        metavar="LEVEL",
        choices=_LOG_LEVELS,
        type=str.upper,
        default=None,
        help=f"Set logging verbosity for this run only. Choices: {', '.join(_LOG_LEVELS)}.",
    )
    parser.add_argument(
        "--no-splash",
        action="store_true",
        help="Skip the loading splash screen (does not change saved settings).",
    )
    parser.add_argument(
        "--config",
        metavar="PATH",
        default=None,
        help="Use an alternate settings file for this run only (your default settings are not modified).",
    )
    parser.add_argument(
        "--dump-settings",
        action="store_true",
        help="Print current settings as JSON and exit.",
    )
    return parser


def _maybe_send_first_run_telemetry(command: str) -> None:
    """Send a one-time cli_first_use event on the first --version or --help invocation.

    Respects VI_NO_TELEMETRY env var and the telemetry.enabled setting.
    Completely best-effort — any failure is silently swallowed.
    """
    if os.environ.get("VI_NO_TELEMETRY"):
        return
    try:
        from vector_inspector.services.settings_service import SettingsService
        from vector_inspector.services.telemetry_service import TelemetryService

        settings = SettingsService()
        if settings.get(_FIRST_RUN_KEY, False):
            return

        telemetry = TelemetryService(settings_service=settings)
        if not telemetry.is_enabled():
            return

        telemetry.queue_event(
            {
                "event_name": "cli_first_use",
                "metadata": {
                    "command": command,
                    "platform": platform.system(),
                    "ts": datetime.now(UTC).isoformat(),
                },
            }
        )
        telemetry.send_batch()
        settings.set(_FIRST_RUN_KEY, True)
    except Exception:
        pass  # Best-effort: never crash the CLI for a telemetry failure


def _handle_dump_settings(config_path: str | None) -> None:
    """Print settings JSON to stdout and exit 0.  Never imports Qt."""
    settings_file = Path(config_path) if config_path else Path.home() / ".vector-inspector" / "settings.json"
    try:
        data = json.loads(settings_file.read_text(encoding="utf-8")) if settings_file.exists() else {}
        print(json.dumps(data, indent=2))  # noqa: T201
    except Exception as exc:
        print(f"Error reading settings: {exc}", file=sys.stderr)  # noqa: T201
        sys.exit(1)
    sys.exit(0)


def parse_cli_args(argv: list[str] | None = None) -> None:
    """Parse CLI arguments, apply runtime-only env vars, and exit where appropriate.

    Must be called before importing Qt/GUI modules.  Returns normally
    (without exiting) when no early-exit flag is supplied.
    """
    argv = sys.argv[1:] if argv is None else argv

    # Step 1: Pre-parse non-exit flags so env vars are set before telemetry
    # fires or --dump-settings reads settings (VI_CONFIG_PATH must be ready).
    pre = argparse.ArgumentParser(add_help=False)
    pre.add_argument("--no-telemetry", action="store_true")
    pre.add_argument("--log-level", type=str.upper, default=None)
    pre.add_argument("--config", default=None)
    pre_ns, _ = pre.parse_known_args(argv)

    if pre_ns.no_telemetry:
        os.environ["VI_NO_TELEMETRY"] = "1"
    if pre_ns.log_level:
        os.environ["LOG_LEVEL"] = pre_ns.log_level
        # Also update the already-imported logger level so the setting takes
        # effect even on code paths that imported logging before this call.
        try:
            import logging

            logging.getLogger("vector_inspector").setLevel(getattr(logging, pre_ns.log_level))
        except Exception:
            pass
    if pre_ns.config:
        os.environ["VI_CONFIG_PATH"] = pre_ns.config

    # Step 2: Detect command for first-run telemetry before argparse exits.
    command: str | None = None
    if "--version" in argv:
        command = "--version"
    elif "--help" in argv or "-h" in argv:
        command = "--help"
    elif "--dump-settings" in argv:
        command = "--dump-settings"

    if command:
        _maybe_send_first_run_telemetry(command)

    # Step 3: Full parse — exits here for --version / --help.
    parser = _build_parser()
    args = parser.parse_args(argv)

    # Step 4: --dump-settings is an early exit (no Qt needed).
    if args.dump_settings:
        _handle_dump_settings(args.config)

    # Step 5: Set remaining runtime env vars.
    if args.no_splash:
        os.environ["VI_NO_SPLASH"] = "1"


def console_entry() -> None:
    """Console script entry point for the ``vector-inspector`` command."""
    parse_cli_args()
    # Only reached when no early-exit flag was given; launch the GUI.
    from vector_inspector.main import main

    main()
