from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QProgressDialog

from vector_inspector.services.settings_service import SettingsService


class LoadingDialog(QProgressDialog):
    def __init__(self, message="Loading...", parent=None):
        super().__init__(message, None, 0, 0, parent)
        self.setWindowTitle("Please Wait")
        self.setWindowModality(Qt.ApplicationModal)
        self.setCancelButton(None)
        self.setMinimumDuration(0)
        self.setAutoClose(False)
        self.setAutoReset(False)
        self.setValue(0)
        self.setMinimumWidth(300)
        # Apply consistent status color from shared styles
        try:
            settings = SettingsService()
            # Apply highlight color only if accent styling is enabled.
            if settings.get_use_accent_enabled():
                color = settings.get_highlight_color()
                # Target the label inside QProgressDialog
                self.setStyleSheet(f"QProgressDialog QLabel {{ color: {color}; }}")
        except Exception:
            pass
        self.reset()  # Hide dialog by default until show_loading() is called

    def show_loading(self, message=None):
        if message:
            self.setLabelText(message)
        self.setValue(0)
        self.show()
        # Force the dialog to render by processing events multiple times
        QApplication.processEvents()
        self.repaint()
        QApplication.processEvents()

    def hide_loading(self):
        self.reset()
        self.hide()
        self.close()
