"""Dialog for installing a missing database provider package.

Shows full installation instructions (individual, recommended, and all-bundle
commands) so the user can copy them manually, and also offers a one-click
"Install Now" option that runs pip in a background thread with live output.

Emits ``provider_installed(provider_id)`` after a successful install so
callers can trigger a provider-list refresh.
"""

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)

from vector_inspector.core.provider_detection import FeatureInfo, ProviderInfo
from vector_inspector.services.provider_install_service import install_feature, install_provider


class _InstallThread(QThread):
    """Background thread that runs pip install and streams output lines."""

    output_line = Signal(str)  # one pip output line at a time
    finished = Signal(int, str)  # (returncode, combined_output)

    def __init__(self, thing: ProviderInfo | FeatureInfo, parent=None) -> None:
        super().__init__(parent)
        self._thing = thing

    def run(self) -> None:
        if isinstance(self._thing, FeatureInfo):
            returncode, combined = install_feature(
                self._thing.id,
                on_output=lambda line: self.output_line.emit(line),
            )
        else:
            returncode, combined = install_provider(
                self._thing.id,
                on_output=lambda line: self.output_line.emit(line),
            )
        self.finished.emit(returncode, combined)


class ProviderInstallDialog(QDialog):
    """Modal dialog for a missing provider.

    States
    ------
    Ready
        Displays full installation instructions (copy-able) and an
        "Install Now" button for the in-app install path.
    Installing
        Hides action buttons, shows an indeterminate progress bar, and streams
        pip output into a read-only log area.
    Success
        Emits ``provider_installed``, updates status to green, shows "Close".
    Failure
        Shows a red error status, re-enables "Retry", and shows "Close".
    """

    provider_installed = Signal(str)  # emits id on success (provider or feature)

    def __init__(self, provider: ProviderInfo | FeatureInfo, parent=None) -> None:
        super().__init__(parent)
        self._provider = provider
        self._thread: _InstallThread | None = None

        self.setWindowTitle(f"Install {provider.name}")
        self.setMinimumWidth(560)
        self.setMinimumHeight(320)
        self._setup_ui()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        # Header
        header = QLabel(f"<b>{self._provider.name}</b> is not currently installed.")
        layout.addWidget(header)

        desc = QLabel(self._provider.description)
        desc.setStyleSheet("color: gray;")
        layout.addWidget(desc)

        # Full install instructions (copy-able, same info as the old QMessageBox)
        instructions_group = QGroupBox("Installation Instructions")
        instructions_layout = QVBoxLayout(instructions_group)

        instructions_edit = QPlainTextEdit()
        instructions_edit.setReadOnly(True)
        instructions_edit.setPlainText(self._build_instructions())
        instructions_edit.setMaximumHeight(160)
        instructions_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        instructions_layout.addWidget(instructions_edit)

        layout.addWidget(instructions_group)

        # In-app install option
        install_group = QGroupBox("Install Now")
        install_group_layout = QVBoxLayout(install_group)

        install_hint = QLabel(
            "Or let Vector Inspector install it for you. "
            "The output will be shown below so you can see what's happening."
        )
        install_hint.setWordWrap(True)
        install_hint.setStyleSheet("color: gray;")
        install_group_layout.addWidget(install_hint)

        layout.addWidget(install_group)

        # Status line (hidden until install starts)
        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._status_label.hide()
        layout.addWidget(self._status_label)

        # Indeterminate progress bar (hidden until install starts)
        self._progress_bar = QProgressBar()
        self._progress_bar.setRange(0, 0)
        self._progress_bar.hide()
        layout.addWidget(self._progress_bar)

        # Output log (hidden until install starts)
        self._output_edit = QPlainTextEdit()
        self._output_edit.setReadOnly(True)
        self._output_edit.setMinimumHeight(160)
        self._output_edit.setStyleSheet("font-family: monospace; font-size: 11px;")
        self._output_edit.hide()
        layout.addWidget(self._output_edit)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self._install_btn = QPushButton("Install Now")
        self._install_btn.setDefault(True)
        self._install_btn.clicked.connect(self._start_install)
        btn_row.addWidget(self._install_btn)

        self._close_btn = QPushButton("Cancel")
        self._close_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._close_btn)

        layout.addLayout(btn_row)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_instructions(self) -> str:
        """Build copy-able installation instructions from the provider/feature object."""
        thing = self._provider
        return (
            f"{thing.name} is not installed.\n\n"
            f"To install it, run:\n\n"
            f"    {thing.install_command}\n\n"
            "Or install the recommended bundle:\n\n"
            "    pip install vector-inspector[recommended]\n\n"
            "Or install everything:\n\n"
            "    pip install vector-inspector[all]\n"
        )

    # ------------------------------------------------------------------
    # Install flow
    # ------------------------------------------------------------------

    def _start_install(self) -> None:
        """Switch to the Installing state and launch the background thread."""
        self._install_btn.setEnabled(False)
        self._install_btn.hide()
        self._close_btn.setEnabled(False)

        self._status_label.setText("Installing…")
        self._status_label.setStyleSheet("color: gray;")
        self._status_label.show()

        self._progress_bar.show()
        self._output_edit.show()
        self.setMinimumHeight(420)
        self.adjustSize()

        self._thread = _InstallThread(self._provider, parent=self)
        self._thread.output_line.connect(self._on_output_line)
        self._thread.finished.connect(self._on_install_finished)
        self._thread.start()

    def _on_output_line(self, line: str) -> None:
        self._output_edit.appendPlainText(line.rstrip())
        self._output_edit.ensureCursorVisible()

    def _on_install_finished(self, returncode: int, _combined: str) -> None:
        self._progress_bar.hide()
        self._close_btn.setEnabled(True)
        self._status_label.show()  # ensure visible whether or not _start_install ran first

        if returncode == 0:
            self._status_label.setText(
                f"✓ {self._provider.name} installed successfully! Close this dialog to continue."
            )
            self._status_label.setStyleSheet("color: green; font-weight: bold;")
            self._close_btn.setText("Close")
            self._close_btn.clicked.disconnect()
            self._close_btn.clicked.connect(self.accept)
            self.provider_installed.emit(self._provider.id)
        else:
            self._status_label.setText(f"✗ Installation failed (exit code {returncode}). See output above for details.")
            self._status_label.setStyleSheet("color: red; font-weight: bold;")
            self._close_btn.setText("Close")
            self._close_btn.clicked.disconnect()
            self._close_btn.clicked.connect(self.reject)
            # Allow retry
            self._install_btn.setText("Retry")
            self._install_btn.show()
            self._install_btn.setEnabled(True)
