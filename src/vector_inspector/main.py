"""Main entry point for Vector Inspector application."""

import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from vector_inspector.ui.main_window import MainWindow
from vector_inspector.core.logging import log_error

# Ensures the app looks in its own folder for the raw libraries
sys.path.append(os.path.dirname(sys.executable))


def main():
    """Launch the Vector Inspector application."""
    app = QApplication(sys.argv)
    app.setApplicationName("Vector Inspector")
    app.setOrganizationName("Vector Inspector")

    def send_ping():
        # Telemetry: send launch ping if enabled
        try:
            from vector_inspector.services.telemetry_service import TelemetryService
            from vector_inspector import get_version, __version__
    
            app_version = None
            try:
                app_version = get_version()
            except Exception:
                app_version = __version__
            telemetry = TelemetryService()
            telemetry.send_launch_ping(app_version=app_version)
        except Exception as e:
            log_error(f"[Telemetry] Failed to send launch ping: {e}")

    window = MainWindow()
    window.show()
    QTimer.singleShot(0, lambda: send_ping())

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
