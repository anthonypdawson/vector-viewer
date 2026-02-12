"""Main entry point for Vector Inspector application.

Run lightweight telemetry before importing any Qt/PySide libraries so we
can record launch attempts even when the GUI dependencies fail to load.
"""

import os
import sys

# Run early telemetry before importing any Qt/PySide modules. Keep this
# minimal and tolerant of failure so missing GUI requirements don't prevent
# the app from reporting an attempted launch.
try:
    from vector_inspector import get_version
    from vector_inspector.services.telemetry_service import TelemetryService

    try:
        telemetry = TelemetryService()
        telemetry.send_launch_ping(app_version=get_version())
    except Exception as _err:
        # Best-effort: avoid raising here so that missing telemetry deps
        # don't stop the application from proceeding.
        try:
            sys.stderr.write(f"[Telemetry] Early send failed: {_err}\n")
        except Exception:
            pass
except Exception:
    # If telemetry or version lookup fail, continue — we still want to
    # attempt to start the app and report later when possible.
    pass

# Defer Qt/PySide imports until after we've attempted early telemetry.

# Ensures the app looks in its own folder for the raw libraries
sys.path.append(os.path.dirname(sys.executable))

# Import lightweight helpers that don't pull in Qt here
from vector_inspector import get_version


def main():
    """Launch the Vector Inspector application."""
    # Get version for telemetry
    app_version = get_version()

    # Set up global exception handlers to catch and report all uncaught exceptions
    try:
        from vector_inspector.utils.exception_handler import setup_global_exception_handler

        setup_global_exception_handler(app_version=app_version)
    except Exception as e:
        # Best-effort: if exception handler setup fails, continue anyway
        try:
            sys.stderr.write(f"[Warning] Failed to set up global exception handler: {e}\n")
        except Exception:
            pass
    # Import Qt/PySide modules only after early telemetry has run.
    try:
        from PySide6.QtWidgets import QApplication

        # UI helpers (these import Qt widgets internally) — import after QApplication
        from vector_inspector.ui.loading_screen import show_loading_screen
    except Exception as _qt_err:
        # Capture traceback and send an Error telemetry event (best-effort)
        import traceback

        tb = traceback.format_exc()
        try:
            from vector_inspector.services.telemetry_service import TelemetryService

            telemetry = TelemetryService()
            telemetry.send_error_event(message=str(_qt_err), tb=tb, app_version=get_version())
        except Exception:
            try:
                sys.stderr.write(
                    f"[Telemetry] Failed sending PySide import error: {_qt_err}\n{tb}\n"
                )
            except Exception:
                pass
        # Re-raise so the import failure surfaces to the caller (app cannot run)
        raise

    app = QApplication(sys.argv)
    app.setApplicationName("Vector Inspector")
    app.setApplicationDisplayName("Vector Inspector")  # For some dialogs and OS integrations
    app.setOrganizationName("Vector Inspector")

    # Set up Qt-specific exception handler for slots/signals
    try:
        from vector_inspector.utils.exception_handler import setup_qt_exception_handler

        setup_qt_exception_handler()
    except Exception as e:
        try:
            sys.stderr.write(f"[Warning] Failed to set up Qt exception handler: {e}\n")
        except Exception:
            pass

    # Set application icon
    from PySide6.QtGui import QIcon

    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "logo.ico")))

    # Show loading screen (if not disabled in settings)
    loading = show_loading_screen(
        app_name="Vector Inspector",
        version=f"v{app_version}",
        tagline="The missing toolset for your vector data",
        loading_text="Initializing providers…",
    )

    # Heavy imports after loading screen is visible
    if loading:
        loading.set_loading_text("Loading main window...")
        app.processEvents()

    from vector_inspector.ui.main_window import MainWindow

    if loading:
        loading.set_loading_text("Preparing interface...")
        app.processEvents()

    window = MainWindow()
    window.show()

    # Always fade out loading screen automatically
    if loading:
        loading.fade_out()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
