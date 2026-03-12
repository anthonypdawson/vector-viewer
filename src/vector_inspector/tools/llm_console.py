"""LLM Console — interactive window for testing the configured LLM provider.

Launched via the hidden CLI flag:

    python -m vector_inspector --llm-console

This is a developer/debug tool and is intentionally absent from --help output.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.logging import log_error, log_info


def _make_provider():
    """Create an LLM provider from the application's saved settings."""
    try:
        from vector_inspector.core.llm_providers.provider_factory import LLMProviderFactory
        from vector_inspector.services.settings_service import SettingsService

        settings = SettingsService()
        provider = LLMProviderFactory.create_from_settings(settings)
        if provider is None:
            log_error("LLM console: provider factory returned None — could not create provider from settings")
            return None

        log_info(
            "LLM console: provider=%s model=%s",
            provider.get_provider_name(),
            provider.get_model_name(),
        )
        return provider
    except Exception as exc:
        log_error("LLM console: could not create provider — %s", exc)
        return None


class _GenerateWorker(QThread):
    """Runs one provider request in a background thread.

    Emits ``chunk`` for each streamed delta, then ``done`` when complete, or
    ``error`` with a plain message string on failure.  Never touches the UI.
    """

    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, provider, messages: list[dict[str, str]], model: str) -> None:
        super().__init__()
        self._provider = provider
        self._messages = messages
        self._model = model

    def run(self) -> None:
        try:
            caps = self._provider.get_capabilities()
            if caps.supports_streaming:
                gen = self._provider.stream_messages(
                    self._messages,
                    model=self._model,
                    request_id="llm-console",
                )
                for ev in gen:
                    if ev.type == "delta":
                        self.chunk.emit(ev.content)
                    elif ev.type == "done":
                        break
            else:
                result = self._provider.generate_messages(self._messages, model=self._model)
                self.chunk.emit(str(result))
        except Exception as exc:
            log_error("LLM console request failed: %s", exc)
            self.error.emit(str(exc))
        finally:
            self.done.emit()


class LLMConsoleWindow(QMainWindow):
    """Chat-style window that drives the active LLM provider interactively.

    Supports multi-turn conversation (history is maintained in memory) and
    streaming responses when the provider advertises streaming support.
    Press Ctrl+Enter (or click Send) to submit a prompt.
    """

    def __init__(self, provider, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("LLM Console  [debug]")
        self.resize(760, 560)

        self._provider = provider
        self._messages: list[dict[str, str]] = []
        self._current_response: str = ""
        self._worker: _GenerateWorker | None = None

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(6)
        layout.setContentsMargins(8, 8, 8, 8)

        # Provider / model status line
        pname = provider.get_provider_name() if provider else "—"
        mname = provider.get_model_name() if provider else "—"
        available = provider.is_available() if provider else False
        status_text = f"Provider: {pname}  •  Model: {mname}  •  {'✓ available' if available else '✗ not available'}"
        self._status = QLabel(status_text)
        self._status.setStyleSheet("color: green; font-size: 11px;" if available else "color: red; font-size: 11px;")
        layout.addWidget(self._status)

        # Chat history (read-only)
        self._history = QTextEdit()
        self._history.setReadOnly(True)
        mono = QFont("Consolas" if sys.platform == "win32" else "Monospace", 10)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._history.setFont(mono)
        layout.addWidget(self._history, stretch=1)

        # Indeterminate progress bar — visible only while waiting for a response
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)  # indeterminate / marquee mode
        self._busy_bar.setFixedHeight(6)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setVisible(False)
        layout.addWidget(self._busy_bar)

        # Input box
        self._input = QTextEdit()
        self._input.setFixedHeight(80)
        self._input.setPlaceholderText("Enter prompt here…  (Ctrl+Enter to send)")
        self._input.installEventFilter(self)
        layout.addWidget(self._input)

        # Button row
        btn_row = QHBoxLayout()
        self._send_btn = QPushButton("Send  (Ctrl+Enter)")
        self._clear_btn = QPushButton("Clear History")
        self._reconnect_btn = QPushButton("Reconnect Provider")
        self._reconnect_btn.setToolTip(
            "Reload the LLM provider from current Settings.\n"
            "Use this after changing provider settings in the main window."
        )
        btn_row.addWidget(self._send_btn, stretch=1)
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._reconnect_btn)
        layout.addLayout(btn_row)

        self._send_btn.clicked.connect(self._send)
        self._clear_btn.clicked.connect(self._clear)
        self._reconnect_btn.clicked.connect(self._reconnect)

    # ------------------------------------------------------------------
    # Event filter — intercept Ctrl+Enter in the input box
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event):
        if (
            obj is self._input
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Return
            and event.modifiers() == Qt.KeyboardModifier.ControlModifier
        ):
            self._send()
            return True
        return super().eventFilter(obj, event)

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    def _send(self) -> None:
        prompt = self._input.toPlainText().strip()
        if not prompt:
            return
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "Still waiting for the previous response.")
            return

        self._input.clear()
        self._messages.append({"role": "user", "content": prompt})
        self._current_response = ""

        self._append_label("You")
        self._append_text(prompt + "\n")
        self._append_label("Assistant")

        self._send_btn.setEnabled(False)
        self._busy_bar.setVisible(True)
        self._status.setText(self._status.text().split("  •  Generating")[0] + "  •  Generating…")
        self._status.setStyleSheet("color: #b8860b; font-size: 11px;")  # dark-yellow while busy

        self._worker = _GenerateWorker(self._provider, list(self._messages), self._provider.get_model_name())
        self._worker.chunk.connect(self._on_chunk)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, text: str) -> None:
        self._current_response += text
        cursor = self._history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._history.setTextCursor(cursor)
        self._history.ensureCursorVisible()

    def _on_done(self) -> None:
        self._append_text("\n\n")
        if self._current_response:
            self._messages.append({"role": "assistant", "content": self._current_response})
        self._current_response = ""
        self._busy_bar.setVisible(False)
        self._restore_status()
        self._send_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._append_text(f"\n[Error: {msg}]\n\n")
        # remove the pending user message that triggered the failure
        if self._messages and self._messages[-1]["role"] == "user":
            self._messages.pop()
        self._current_response = ""
        self._busy_bar.setVisible(False)
        self._restore_status()
        self._send_btn.setEnabled(True)

    def _restore_status(self) -> None:
        """Reset the status label to reflect current provider availability."""
        p = self._provider
        pname = p.get_provider_name() if p else "—"
        mname = p.get_model_name() if p else "—"
        available = p.is_available() if p else False
        avail_text = "✓ available" if available else "✗ not available"
        self._status.setText(f"Provider: {pname}  •  Model: {mname}  •  {avail_text}")
        self._status.setStyleSheet("color: green; font-size: 11px;" if available else "color: red; font-size: 11px;")

    def _clear(self) -> None:
        self._history.clear()
        self._messages.clear()
        self._current_response = ""

    def _reconnect(self) -> None:
        """Rebuild the provider from saved settings and refresh the status bar."""
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "Busy", "Cannot reconnect while a request is in progress.")
            return

        self._reconnect_btn.setEnabled(False)
        self._reconnect_btn.setText("Reconnecting…")
        QApplication.processEvents()

        new_provider = _make_provider()
        if new_provider is None:
            QMessageBox.critical(
                self,
                "Reconnect Failed",
                "Could not create a provider from current settings.\n\nCheck Settings → LLM.",
            )
            self._reconnect_btn.setEnabled(True)
            self._reconnect_btn.setText("Reconnect Provider")
            return

        self._provider = new_provider
        pname = new_provider.get_provider_name()
        mname = new_provider.get_model_name()
        available = new_provider.is_available()
        avail_text = "✓ available" if available else "✗ not available"
        self._status.setText(f"Provider: {pname}  •  Model: {mname}  •  {avail_text}")
        self._status.setStyleSheet("color: green; font-size: 11px;" if available else "color: red; font-size: 11px;")

        self._messages.clear()
        self._append_text(f"[Reconnected → {pname} / {mname}]\n\n")

        self._reconnect_btn.setEnabled(True)
        self._reconnect_btn.setText("Reconnect Provider")

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _append_label(self, speaker: str) -> None:
        """Insert a bold speaker label (e.g. 'You:') at the cursor end."""
        cursor = self._history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f"<b>{speaker}:</b> ")
        self._history.setTextCursor(cursor)

    def _append_text(self, text: str) -> None:
        """Insert plain text at the cursor end (HTML-safe)."""
        cursor = self._history.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._history.setTextCursor(cursor)
        self._history.ensureCursorVisible()


def launch() -> None:
    """Open (or reuse an existing) QApplication and show the LLM console.

    When called from *within* the main app process (QApplication already
    exists) the window is simply shown as a floating top-level widget.
    When invoked standalone via ``--llm-console`` a fresh QApplication is
    created and the function exits with the event-loop return code.
    """
    created_app = QApplication.instance() is None
    if created_app:
        app = QApplication(sys.argv)
        app.setApplicationName("Vector Inspector — LLM Console")
    else:
        app = QApplication.instance()

    provider = _make_provider()
    if provider is None:
        QMessageBox.critical(
            None,
            "LLM Console",
            "Could not create an LLM provider.\n\nCheck Settings → LLM to configure a provider.",
        )
        if created_app:
            sys.exit(1)
        return

    win = LLMConsoleWindow(provider)
    win.show()

    if created_app:
        sys.exit(app.exec())
