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
    parser.add_argument(
        "--llm-console",
        action="store_true",
        help=argparse.SUPPRESS,  # Hidden debug/dev flag — not shown in --help
    )
    parser.add_argument(
        "--install",
        metavar="PROVIDER",
        nargs="?",
        const="_wizard_",
        default=None,
        help=(
            "Install a database provider package without launching the GUI. "
            "Pass a provider ID (e.g. chromadb, qdrant, pinecone, lancedb, pgvector, "
            "weaviate, milvus) or omit the value to run an interactive wizard that lists "
            "all unavailable providers."
        ),
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


def _handle_install(provider_arg: str) -> None:
    """Interactive or direct provider install wizard.  Never imports Qt.

    When ``provider_arg`` is ``"_wizard_"`` (the const from ``--install``
    with no value), an interactive numbered menu is shown.  Otherwise
    ``provider_arg`` is treated as a provider ID and installed directly.
    """
    from vector_inspector.core.provider_detection import get_all_providers
    from vector_inspector.services.provider_install_service import (
        _VALID_PROVIDER_IDS,
        get_install_command,
        install_provider,
    )

    _DIVIDER = "=" * 54

    print("\nVector Inspector — Provider Installer")  # noqa: T201
    print(_DIVIDER)  # noqa: T201
    print("Checking installed providers…")  # noqa: T201

    all_providers = get_all_providers()
    unavailable = [p for p in all_providers if not p.available]
    available = [p for p in all_providers if p.available]

    if available:
        print(f"Already installed: {', '.join(p.name for p in available)}")  # noqa: T201

    if provider_arg == "_wizard_":
        # Interactive wizard mode — list unavailable providers and ask.
        if not unavailable:
            print("\n✓ All providers are already installed!")  # noqa: T201
            sys.exit(0)

        print("\nAvailable to install:")  # noqa: T201
        for idx, p in enumerate(unavailable, start=1):
            print(f"  {idx}. {p.name:<30} ({p.install_command})")  # noqa: T201

        print()  # noqa: T201
        try:
            raw = input("Enter a number or provider ID (or press Enter to cancel): ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")  # noqa: T201
            sys.exit(0)

        if not raw:
            print("Cancelled.")  # noqa: T201
            sys.exit(0)

        # Accept a number from the menu or a literal provider ID.
        selected_provider = None
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(unavailable):
                selected_provider = unavailable[idx]
        if selected_provider is None:
            # Try as a direct provider ID.
            matches = [p for p in unavailable if p.id == raw]
            if matches:
                selected_provider = matches[0]

        if selected_provider is None:
            print(f"Unknown selection: {raw!r}. Aborting.", file=sys.stderr)  # noqa: T201
            sys.exit(1)
    else:
        # Direct mode — the user passed a provider ID on the command line.
        if provider_arg not in _VALID_PROVIDER_IDS:
            print(  # noqa: T201
                f"Unknown provider: {provider_arg!r}\nValid providers: {', '.join(sorted(_VALID_PROVIDER_IDS))}",
                file=sys.stderr,
            )
            sys.exit(1)

        matches = [p for p in all_providers if p.id == provider_arg]
        selected_provider = matches[0] if matches else None
        if selected_provider is None:
            print(f"Provider info not found for {provider_arg!r}.", file=sys.stderr)  # noqa: T201
            sys.exit(1)

        if selected_provider.available:
            print(f"\n✓ {selected_provider.name} is already installed.")  # noqa: T201
            sys.exit(0)

    # Run the install.
    cmd = get_install_command(selected_provider.id)
    print(f"\nInstalling {selected_provider.name}…")  # noqa: T201
    print(f"Running: {' '.join(cmd)}")  # noqa: T201
    print(_DIVIDER)  # noqa: T201

    returncode, _combined = install_provider(
        selected_provider.id,
        on_output=lambda line: print(line, end="", flush=True),  # noqa: T201
    )

    print(_DIVIDER)  # noqa: T201
    if returncode == 0:
        print(f"\n✓ {selected_provider.name} installed successfully!")  # noqa: T201
        print("Restart Vector Inspector (or use the 🔄 Refresh button) to use it.")  # noqa: T201
        sys.exit(0)
    else:
        print(f"\n✗ Installation failed (exit code {returncode}).", file=sys.stderr)  # noqa: T201
        sys.exit(returncode)


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

    # Step 4b: --install is an early exit (no Qt needed).
    if args.install is not None:
        _handle_install(args.install)

    # Step 5: Set remaining runtime env vars.
    if args.no_splash:
        os.environ["VI_NO_SPLASH"] = "1"
    if args.llm_console:
        os.environ["VI_LLM_CONSOLE"] = "1"


def console_entry() -> None:
    """Console script entry point for the ``vector-inspector`` command."""
    parse_cli_args()
    # Only reached when no early-exit flag was given; launch the GUI.
    # --llm-console (VI_LLM_CONSOLE=1) causes main.py to also open the
    # LLM debug window alongside the main application window.
    from vector_inspector.main import main

    main()
