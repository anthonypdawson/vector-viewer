from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QPushButton, QTextEdit, QHBoxLayout
from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices, QCursor
from PySide6.QtCore import QUrl


class UpdateDetailsDialog(QDialog):
    def __init__(
        self, version: str, release_notes: str, pip_command: str, github_url: str, parent=None
    ):
        super().__init__(parent)
        self.setWindowTitle(f"Update Available: v{version}")
        self.setMinimumWidth(500)
        layout = QVBoxLayout(self)

        title = QLabel(f"<b>New version available: v{version}</b>")
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        notes_label = QLabel("<b>Release Notes:</b>")
        layout.addWidget(notes_label)

        notes = QTextEdit()
        notes.setReadOnly(True)
        notes.setPlainText(release_notes)
        layout.addWidget(notes)

        # Add vertical space before update instructions
        from PySide6.QtWidgets import QSpacerItem, QSizePolicy

        layout.addSpacing(16)

        pip_label = QLabel(f"<b>Update with pip:</b> <code>{pip_command}</code>")
        layout.addWidget(pip_label)

        btn_layout = QHBoxLayout()
        github_btn = QPushButton("View on GitHub")
        github_btn.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(github_url)))
        btn_layout.addWidget(github_btn)

        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
