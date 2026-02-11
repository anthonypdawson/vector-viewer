"""Main entry point for Vector Inspector application."""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from vector_inspector import get_version
from vector_inspector.ui.loading_screen import show_loading_screen

# Ensures the app looks in its own folder for the raw libraries
sys.path.append(os.path.dirname(sys.executable))


def main():
    """Launch the Vector Inspector application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Inspector")
    app.setApplicationDisplayName("Vector Inspector")  # For some dialogs and OS integrations
    app.setOrganizationName("Vector Inspector")
    # Set application icon
    from PySide6.QtGui import QIcon

    app.setWindowIcon(QIcon(os.path.join(os.path.dirname(__file__), "..", "assets", "logo.ico")))

    # Get version once for all uses
    app_version = get_version()

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

    from vector_inspector.core.logging import log_error
    from vector_inspector.ui.main_window import MainWindow

    def send_ping():
        # Telemetry: send launch ping if enabled
        try:
            from vector_inspector.services.telemetry_service import TelemetryService

            telemetry = TelemetryService()
            telemetry.send_launch_ping(app_version=app_version)
        except Exception as e:
            log_error(f"[Telemetry] Failed to send launch ping: {e}")

    if loading:
        loading.set_loading_text("Preparing interface...")
        app.processEvents()

    window = MainWindow()
    window.show()

    # Always fade out loading screen automatically
    if loading:
        loading.fade_out()

    QTimer.singleShot(0, lambda: send_ping())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
