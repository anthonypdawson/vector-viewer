from PySide6.QtWidgets import QProgressDialog, QApplication
from PySide6.QtCore import Qt

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
