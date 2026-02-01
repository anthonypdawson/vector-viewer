"""Main entry point for Vector Inspector application."""

import os
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from vector_inspector import get_version
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.ui.loading_screen import LoadingScreen

# Ensures the app looks in its own folder for the raw libraries
sys.path.append(os.path.dirname(sys.executable))


def main():
    """Launch the Vector Inspector application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Inspector")
    app.setOrganizationName("Vector Inspector")

    # Get version once for all uses
    app_version = get_version()

    # Check if user wants to skip loading screen
    settings = SettingsService()
    show_loading = not settings.get("hide_loading_screen", False)

    # Get the logo path relative to this module
    module_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logo_path = os.path.join(module_dir, "assets", "logo.png")

    loading = None
    if show_loading:
        loading = LoadingScreen(
            logo_path=logo_path,
            version=f"v{app_version}",
            tagline="Vector-Inspector\nThe missing toolset for your vector data",
            loading_text="Initializing providers…",
        )
        loading.show()

        # Force the loading screen to render before continuing
        app.processEvents()

        # NOW do the heavy imports after loading screen is visible
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
