"""Ask the AI dialog for the Search Results panel.

Provides a streaming LLM response window pre-loaded with the current search
context (query, top-N results, selected item).  Launched from the Search view
toolbar ("Ask the AI") or the right-click "Explain result" shortcut.

Usage::

    ctx = build_search_context(search_input, search_results, selected_row=row)
    prefilled = build_explain_prompt(ctx.get("selected_result"))
    dlg = AskAIDialog(app_state, context=ctx, prefilled_prompt=prefilled, parent=self)
    dlg.show()
"""

from __future__ import annotations

import sys
from typing import Any

from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtGui import QFont, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
)

from vector_inspector.core.logging import log_error
from vector_inspector.services.search_ai_service import build_messages
from vector_inspector.state import AppState


class _SearchAIWorker(QThread):
    """Background thread that sends a prompt to the LLM provider and streams deltas.

    Follows the same pattern as ``_GenerateWorker`` in ``tools/llm_console.py``.
    Never touches the UI directly — communicates only via signals.
    """

    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, provider: Any, messages: list[dict[str, str]]) -> None:
        super().__init__()
        self._provider = provider
        self._messages = messages

    def run(self) -> None:
        try:
            caps = self._provider.get_capabilities()
            model = self._provider.get_model_name()
            if caps.supports_streaming:
                for ev in self._provider.stream_messages(self._messages, model=model, request_id="ask-ai"):
                    if ev.type == "delta":
                        self.chunk.emit(ev.content)
                    elif ev.type == "done":
                        break
            else:
                result = self._provider.generate_messages(self._messages, model=model)
                self.chunk.emit(str(result))
        except Exception as exc:
            log_error("Ask the AI request failed: %s", exc, exc_info=True)
            self.error.emit(str(exc))
        finally:
            self.done.emit()


class AskAIDialog(QDialog):
    """Modal dialog that lets users ask questions about their search results.

    The dialog is pre-loaded with the current search context (query, top-N
    results, optionally the selected result) and a prefilled prompt which the
    user can edit before sending.  Responses are streamed in real time from
    the configured LLM provider.

    Args:
        app_state: Application state providing ``llm_provider``.
        context: Payload from :func:`~vector_inspector.services.search_ai_service.build_search_context`.
        prefilled_prompt: Optional text to pre-populate the prompt input.
        parent: Parent widget.
    """

    def __init__(
        self,
        app_state: AppState,
        context: dict[str, Any],
        prefilled_prompt: str = "",
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ask the AI — Search Context")
        self.resize(720, 560)
        self.setModal(False)  # Non-modal so user can keep browsing results

        self._app_state = app_state
        self._context = context
        self._worker: _SearchAIWorker | None = None

        self._setup_ui(prefilled_prompt)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self, prefilled_prompt: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Provider status bar
        self._status_label = QLabel()
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        self._refresh_status_label()
        layout.addWidget(self._status_label)

        # Context preview group (collapsible via checkable group box)
        ctx_group = QGroupBox("Attached context  (click to expand / collapse)")
        ctx_group.setCheckable(True)
        ctx_group.setChecked(False)
        ctx_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        ctx_layout = QVBoxLayout(ctx_group)
        self._context_preview = QTextEdit()
        self._context_preview.setReadOnly(True)
        self._context_preview.setMaximumHeight(130)
        mono = QFont("Consolas" if sys.platform == "win32" else "Monospace", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)
        self._context_preview.setFont(mono)
        self._context_preview.setPlainText(self._render_context_preview())
        ctx_layout.addWidget(self._context_preview)
        # Wire collapse/expand
        self._context_preview.setVisible(False)
        ctx_group.toggled.connect(self._context_preview.setVisible)
        layout.addWidget(ctx_group)

        # Response area (read-only, monospace)
        resp_group = QGroupBox("Response")
        resp_layout = QVBoxLayout(resp_group)
        self._response_area = QTextEdit()
        self._response_area.setReadOnly(True)
        self._response_area.setFont(mono)
        self._response_area.setPlaceholderText("AI response will appear here…")
        resp_layout.addWidget(self._response_area)
        layout.addWidget(resp_group, stretch=1)

        # Indeterminate progress bar — visible only while streaming
        self._busy_bar = QProgressBar()
        self._busy_bar.setRange(0, 0)
        self._busy_bar.setFixedHeight(5)
        self._busy_bar.setTextVisible(False)
        self._busy_bar.setVisible(False)
        layout.addWidget(self._busy_bar)

        # Prompt input
        self._prompt_input = QTextEdit()
        self._prompt_input.setFixedHeight(72)
        self._prompt_input.setPlaceholderText("Ask a question about these results…  (Ctrl+Enter to send)")
        self._prompt_input.installEventFilter(self)
        if prefilled_prompt:
            self._prompt_input.setPlainText(prefilled_prompt)
            # Select all so the user can immediately type over it
            self._prompt_input.selectAll()
        layout.addWidget(self._prompt_input)

        # Button row
        btn_row = QHBoxLayout()
        self._send_btn = QPushButton("Send  (Ctrl+Enter)")
        self._send_btn.setDefault(True)
        self._clear_btn = QPushButton("Clear")
        self._close_btn = QPushButton("Close")
        btn_row.addWidget(self._send_btn, stretch=1)
        btn_row.addWidget(self._clear_btn)
        btn_row.addWidget(self._close_btn)
        layout.addLayout(btn_row)

        self._send_btn.clicked.connect(self._send)
        self._clear_btn.clicked.connect(self._clear_response)
        self._close_btn.clicked.connect(self.close)

    # ------------------------------------------------------------------
    # Event filter — Ctrl+Enter shortcut in prompt input
    # ------------------------------------------------------------------

    def eventFilter(self, obj, event) -> bool:
        if (
            obj is self._prompt_input
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
        prompt = self._prompt_input.toPlainText().strip()
        if not prompt:
            return
        if self._worker and self._worker.isRunning():
            return  # Silently ignore — button is disabled while busy

        provider = self._get_provider()
        if provider is None:
            self._append_error("No LLM provider is available. Check Settings → LLM.")
            return

        messages = build_messages(prompt, self._context)

        self._send_btn.setEnabled(False)
        self._busy_bar.setVisible(True)

        self._worker = _SearchAIWorker(provider, messages)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_chunk(self, text: str) -> None:
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(text)
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()

    def _on_done(self) -> None:
        # Add a blank line between turns
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText("\n\n")
        self._response_area.setTextCursor(cursor)
        self._busy_bar.setVisible(False)
        self._send_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._append_error(msg)
        self._busy_bar.setVisible(False)
        self._send_btn.setEnabled(True)

    def _clear_response(self) -> None:
        self._response_area.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_provider(self) -> Any | None:
        try:
            provider = self._app_state.llm_provider
            if provider and provider.is_available():
                return provider
            return provider  # Return even if unavailable; provider will surface error
        except Exception as exc:
            log_error("Could not get LLM provider: %s", exc)
            return None

    def _refresh_status_label(self) -> None:
        try:
            provider = self._app_state.llm_provider
            if provider:
                pname = provider.get_provider_name()
                mname = provider.get_model_name()
                available = provider.is_available()
                status = f"Provider: {pname}  •  Model: {mname}  •  {'✓ available' if available else '✗ not available'}"
                color = "green" if available else "#d9534f"
            else:
                status = "No LLM provider configured — check Settings → LLM"
                color = "#d9534f"
        except Exception:
            status = "Provider status unknown"
            color = "gray"
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _append_error(self, msg: str) -> None:
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(f'<span style="color: #d9534f;">[Error: {msg}]</span><br><br>')
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()
        full_msg = f"Ask the AI error: {msg}"
        log_error(full_msg)
        self._status_label.setText("Error — hover for details")
        self._status_label.setToolTip(msg)
        self._status_label.setStyleSheet("color: #d9534f; font-size: 11px;")

    def _render_context_preview(self) -> str:
        """Render a short plain-text summary of the attached context."""
        ctx = self._context
        lines = [f"Search input: {ctx.get('search_input', '')!r}"]
        top = ctx.get("top_results", [])
        if top:
            lines.append(f"Top {len(top)} result(s) attached:")
            for item in top[:3]:
                score = f"{item['score']:.4f}" if item["score"] is not None else "N/A"
                lines.append(f"  #{item['rank']} id={item['id']!r}  score={score}")
            if len(top) > 3:
                lines.append(f"  … and {len(top) - 3} more")
        selected = ctx.get("selected_result")
        if selected:
            score = f"{selected['score']:.4f}" if selected["score"] is not None else "N/A"
            lines.append(f"Selected: #{selected['rank']} id={selected['id']!r}  score={score}")
        return "\n".join(lines)
