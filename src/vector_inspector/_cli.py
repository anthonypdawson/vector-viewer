"""Lightweight CLI argument parsing for Vector Inspector.

Handles --version and --help before any Qt/GUI modules are imported so that
first-run telemetry can be recorded without starting the application.
"""

import argparse
import platform
import sys
from datetime import datetime, timezone

from vector_inspector import get_version

GITHUB_URL = "https://github.com/anthonypdawson/vector-inspector"
_FIRST_RUN_KEY = "cli.first_run_done"


def _build_parser() -> argparse.ArgumentParser:
    return argparse.ArgumentParser(
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


def _maybe_send_first_run_telemetry(command: str) -> None:
    """Send a one-time cli_first_use event on the first --version or --help invocation.

    Respects the telemetry.enabled setting and is completely best-effort —
    any failure is silently swallowed so the CLI never crashes here.
    """
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
                    "ts": datetime.now(timezone.utc).isoformat(),
                },
            }
        )
        telemetry.send_batch()
        settings.set(_FIRST_RUN_KEY, True)
    except Exception:
        pass  # Best-effort: never crash the CLI for a telemetry failure


def parse_cli_args(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and exit if --version or --help was requested.

    Must be called before importing Qt/GUI modules.  Returns normally
    (without exiting) when no recognised CLI flag is supplied.
    """
    argv = sys.argv[1:] if argv is None else argv

    # Detect flags early so telemetry fires before argparse calls sys.exit()
    command: str | None = None
    if "--version" in argv:
        command = "--version"
    elif "--help" in argv or "-h" in argv:
        command = "--help"

    if command:
        _maybe_send_first_run_telemetry(command)

    parser = _build_parser()
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    parser.parse_args(argv)


def console_entry() -> None:
    """Console script entry point for the ``vector-inspector`` command."""
    parse_cli_args()
    # Only reached when no --version/--help flag was given; launch the GUI.
    from vector_inspector.main import main

    main()
