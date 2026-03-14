"""Ask the AI dialog for the Search Results panel.

Provides a streaming LLM response window pre-loaded with the current search
context (query, top-N results, selected item).  Launched from the Search view
toolbar ("Ask the AI") or the right-click "Explain result" shortcut.

Usage::

    ctx = build_search_context(search_input, search_results, selected_row=row)
    prefilled = build_explain_prompt(ctx.get("selected_result"))
    dlg = AskAIDialog(
        app_state,
        context=ctx,
        prefilled_prompt=prefilled,
        all_results=search_results,
        initial_row_indices=[0, 1, 2],
        parent=self,
    )
    dlg.show()
"""

from __future__ import annotations

import html
import sys
from typing import Any

from PySide6.QtCore import QEvent, Qt, QThread, Signal
from PySide6.QtGui import QColor, QFont, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import (
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from vector_inspector.core.logging import log_error
from vector_inspector.services.search_ai_service import (
    LLM_CONTEXT_MAX,
    LLM_CONTEXT_WARN,
    build_messages,
    build_search_context,
    estimate_tokens,
)
from vector_inspector.state import AppState


class _SearchAIWorker(QThread):
    """Background thread that sends a prompt to the LLM provider and streams deltas.

    Follows the same pattern as ``_GenerateWorker`` in ``tools/llm_console.py``.
    Never touches the UI directly — communicates only via signals.
    """

    chunk = Signal(str)
    done = Signal()
    error = Signal(str)

    def __init__(self, provider: Any, messages: list[dict[str, str]], parent=None) -> None:
        super().__init__(parent)
        self._provider = provider
        self._messages = messages

    def run(self) -> None:
        try:
            caps = self._provider.get_capabilities()
            model = self._provider.get_model_name()
            if caps.supports_streaming:
                for ev in self._provider.stream_messages(self._messages, model=model, request_id="ask-ai"):
                    if self.isInterruptionRequested():
                        break
                    if ev.type == "delta":
                        self.chunk.emit(ev.content)
                    elif ev.type == "done":
                        break
            else:
                if not self.isInterruptionRequested():
                    result = self._provider.generate_messages(self._messages, model=model)
                    self.chunk.emit(str(result))
        except Exception as exc:
            log_error("Ask the AI request failed: %s", exc, exc_info=True)
            self.error.emit(str(exc))
        finally:
            self.done.emit()


class AskAIDialog(QDialog):
    """Non-modal dialog that lets users ask questions about their search results.

    The dialog is pre-loaded with the current search context (query, selected
    results, optionally the selected result) and a prefilled prompt which the
    user can edit before sending.  Responses are streamed in real time from
    the configured LLM provider.

    When ``all_results`` is provided the user can interactively change which
    results are included in the context via a checkable list and range
    quick-selectors.  The estimated token count updates in real time.

    Args:
        app_state: Application state providing ``llm_provider``.
        context: Initial payload from
                 :func:`~vector_inspector.services.search_ai_service.build_search_context`.
        prefilled_prompt: Optional text to pre-populate the prompt input.
        all_results: Full raw search results dict — when supplied the result
                     selection section is shown so the user can change which
                     rows are sent to the LLM.
        initial_row_indices: 0-based indices of the results pre-selected on
                             open.  Resets to this list every time the dialog
                             is opened.  Defaults to the first
                             :data:`~vector_inspector.services.search_ai_service.LLM_CONTEXT_MAX`
                             results when not provided.
        parent: Parent widget.
    """

    def __init__(
        self,
        app_state: AppState,
        context: dict[str, Any],
        prefilled_prompt: str = "",
        all_results: dict[str, Any] | None = None,
        initial_row_indices: list[int] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Ask the AI — Search Context")
        self.resize(760, 620)
        self.setModal(False)  # Non-modal so user can keep browsing results
        self.setAttribute(Qt.WA_DeleteOnClose, True)

        self._app_state = app_state
        self._context = context
        self._worker: _SearchAIWorker | None = None

        # Result-selection state (only active when all_results is supplied)
        self._all_results = all_results
        self._search_input: str = context.get("search_input", "")
        # Pre-compute per-row display data from all_results for the list widget
        self._all_row_data: list[dict[str, Any]] = self._extract_all_row_data() if all_results else []

        # Determine initial selection indices; default to first LLM_CONTEXT_MAX rows when omitted
        if initial_row_indices is not None:
            self._initial_row_indices: list[int] = list(initial_row_indices)
        elif self._all_row_data:
            default_count = min(LLM_CONTEXT_MAX, len(self._all_row_data))
            self._initial_row_indices = list(range(default_count))
        else:
            self._initial_row_indices = []
        self._row_indices: list[int] = list(self._initial_row_indices)

        self._setup_ui(prefilled_prompt)

        # Refresh status whenever any LLM setting changes while the dialog is open
        try:
            app_state.settings_service.signals.setting_changed.connect(self._on_setting_changed)
        except AttributeError:
            pass  # settings_service may not be wired in all test contexts
        except Exception as exc:
            log_error("Could not connect setting_changed signal: %s", exc, exc_info=True)

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:
        """Refresh provider status each time the dialog becomes visible."""
        super().showEvent(event)
        try:
            self._app_state.llm_runtime_manager.refresh()
        except AttributeError:
            pass
        self._refresh_status_label()

    def closeEvent(self, event) -> None:
        """Stop any running worker thread before the dialog is destroyed."""
        if self._worker and self._worker.isRunning():
            try:
                self._worker.requestInterruption()
            except Exception:
                pass
            if self._worker.isRunning():
                try:
                    self._worker.quit()
                except Exception:
                    pass
            self._worker.wait(2000)
        super().closeEvent(event)

    def _on_setting_changed(self, key: str, _value: object) -> None:
        """Invalidate the cached LLM provider and update the status bar when an LLM setting changes."""
        if key.startswith("llm."):
            try:
                self._app_state.llm_runtime_manager.refresh()
            except AttributeError:
                pass
            self._refresh_status_label()

    def _setup_ui(self, prefilled_prompt: str) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)

        # Provider status row: label + optional "Configure LLM" button
        status_row = QHBoxLayout()
        self._status_label = QLabel()
        self._status_label.setTextFormat(Qt.TextFormat.PlainText)
        status_row.addWidget(self._status_label, stretch=1)
        self._configure_llm_btn = QPushButton("Configure LLM…")
        self._configure_llm_btn.setFixedWidth(130)
        self._configure_llm_btn.setToolTip("Open Settings to configure an LLM provider")
        self._configure_llm_btn.clicked.connect(self._open_settings)
        self._configure_llm_btn.setVisible(False)
        status_row.addWidget(self._configure_llm_btn)
        layout.addLayout(status_row)
        self._refresh_status_label()

        mono = QFont("Consolas" if sys.platform == "win32" else "Monospace", 9)
        mono.setStyleHint(QFont.StyleHint.Monospace)

        # Result selection group — only shown when all_results was provided
        if self._all_results and self._all_row_data:
            sel_group = QGroupBox("Result selection  (check rows to include in context)")
            sel_group.setCheckable(True)
            sel_group.setChecked(True)
            sel_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            sel_layout = QVBoxLayout(sel_group)

            # Checkable result list
            self._results_list = QListWidget()
            self._results_list.setMaximumHeight(130)
            self._results_list.setFont(mono)
            self._populate_results_list()
            self._results_list.itemChanged.connect(self._on_list_item_changed)
            sel_layout.addWidget(self._results_list)

            # Range quick-select row
            range_row = QHBoxLayout()
            range_row.addWidget(QLabel("Range:"))
            self._range_from = QSpinBox()
            self._range_from.setMinimum(1)
            self._range_from.setMaximum(len(self._all_row_data))
            self._range_from.setValue(1)
            range_row.addWidget(self._range_from)
            range_row.addWidget(QLabel("to"))
            self._range_to = QSpinBox()
            self._range_to.setMinimum(1)
            self._range_to.setMaximum(len(self._all_row_data))
            self._range_to.setValue(min(LLM_CONTEXT_MAX, len(self._all_row_data)))
            range_row.addWidget(self._range_to)
            apply_range_btn = QPushButton("Apply Range")
            apply_range_btn.setFixedWidth(90)
            apply_range_btn.clicked.connect(self._apply_range)
            range_row.addWidget(apply_range_btn)
            reset_btn = QPushButton("Reset to Default")
            reset_btn.setFixedWidth(110)
            reset_btn.setToolTip(f"Reset selection to the default top {LLM_CONTEXT_MAX} results")
            reset_btn.clicked.connect(self._reset_selection)
            range_row.addWidget(reset_btn)
            range_row.addStretch()
            sel_layout.addLayout(range_row)

            # Token count + warning labels
            info_row = QHBoxLayout()
            self._token_label = QLabel()
            self._token_label.setStyleSheet("color: gray; font-size: 11px;")
            info_row.addWidget(self._token_label)
            self._warn_label = QLabel()
            self._warn_label.setStyleSheet("color: #d9534f; font-size: 11px;")
            self._warn_label.setVisible(False)
            info_row.addWidget(self._warn_label)
            info_row.addStretch()
            sel_layout.addLayout(info_row)

            sel_group.toggled.connect(self._results_list.setVisible)
            layout.addWidget(sel_group)

            self._update_token_label()
        else:
            self._results_list = None  # type: ignore[assignment]
            self._token_label = None  # type: ignore[assignment]
            self._warn_label = None  # type: ignore[assignment]

        # Context preview group (collapsible via checkable group box)
        ctx_group = QGroupBox("Attached context  (click to expand / collapse)")
        ctx_group.setCheckable(True)
        ctx_group.setChecked(False)  # Collapsed by default when selection UI is shown
        ctx_group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        ctx_layout = QVBoxLayout(ctx_group)
        self._context_preview = QTextEdit()
        self._context_preview.setReadOnly(True)
        self._context_preview.setMaximumHeight(130)
        self._context_preview.setFont(mono)
        self._context_preview.setPlainText(self._render_context_preview())
        ctx_layout.addWidget(self._context_preview)
        self._context_preview.setVisible(False)
        ctx_group.toggled.connect(self._context_preview.setVisible)
        layout.addWidget(ctx_group)

        # Response area (read-only, monospace)
        resp_group = QGroupBox("Conversation")
        resp_layout = QVBoxLayout(resp_group)
        self._response_area = QTextEdit()
        self._response_area.setReadOnly(True)
        self._response_area.setFont(mono)
        self._response_area.setPlaceholderText("Your question and the AI response will appear here…")
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
    # Result selection helpers
    # ------------------------------------------------------------------

    def _extract_all_row_data(self) -> list[dict[str, Any]]:
        """Extract per-row display data from the raw search results."""
        if not self._all_results:
            return []

        def _unwrap(key: str) -> list:
            val = self._all_results.get(key)  # type: ignore[union-attr]
            if not val:
                return []
            if isinstance(val, list) and val and isinstance(val[0], (list, tuple)):
                return list(val[0])
            return list(val)

        ids = _unwrap("ids")
        documents = _unwrap("documents")
        distances = _unwrap("distances")
        rows = []
        for i, item_id in enumerate(ids):
            doc = documents[i] if i < len(documents) else ""
            dist = distances[i] if i < len(distances) else None
            score_str = f"{dist:.4f}" if dist is not None else "N/A"
            snippet = str(doc or "")[:60].replace("\n", " ")
            rows.append({"idx": i, "id": str(item_id), "distance": score_str, "snippet": snippet})
        return rows

    def _populate_results_list(self) -> None:
        """Fill the QListWidget with one checkable entry per result row."""
        if self._results_list is None:
            return
        selected_set = set(self._row_indices)
        self._results_list.blockSignals(True)
        self._results_list.clear()
        for r in self._all_row_data:
            text = f"#{r['idx'] + 1:>3}  distance={r['distance']}  {r['snippet']}"
            item = QListWidgetItem(text)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if r["idx"] in selected_set else Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, r["idx"])
            self._results_list.addItem(item)
        self._results_list.blockSignals(False)

    def _on_list_item_changed(self, item: QListWidgetItem) -> None:
        """Rebuild context and update token label when a checkbox is toggled."""
        self._sync_row_indices_from_list()
        self._rebuild_context()
        self._update_token_label()

    def _sync_row_indices_from_list(self) -> None:
        """Read checked state from list widget into ``self._row_indices``."""
        if self._results_list is None:
            return
        indices = []
        for i in range(self._results_list.count()):
            it = self._results_list.item(i)
            if it and it.checkState() == Qt.CheckState.Checked:
                idx = it.data(Qt.ItemDataRole.UserRole)
                if idx is not None:
                    indices.append(idx)
        self._row_indices = sorted(indices)

    def _apply_range(self) -> None:
        """Check rows within the range spinbox values (1-based, inclusive)."""
        if self._results_list is None:
            return
        lo = self._range_from.value() - 1  # convert to 0-based
        hi = self._range_to.value() - 1
        if lo > hi:
            lo, hi = hi, lo
        self._results_list.blockSignals(True)
        for i in range(self._results_list.count()):
            it = self._results_list.item(i)
            if it is None:
                continue
            idx = it.data(Qt.ItemDataRole.UserRole)
            state = Qt.CheckState.Checked if lo <= idx <= hi else Qt.CheckState.Unchecked
            it.setCheckState(state)
        self._results_list.blockSignals(False)
        self._sync_row_indices_from_list()
        self._rebuild_context()
        self._update_token_label()

    def _reset_selection(self) -> None:
        """Reset selection to the initial row indices (default top N)."""
        self._row_indices = list(self._initial_row_indices)
        self._populate_results_list()
        self._rebuild_context()
        self._update_token_label()

    def _rebuild_context(self) -> None:
        """Rebuild ``self._context`` from the currently selected row indices."""
        if not self._all_results:
            return
        self._context = build_search_context(
            search_input=self._search_input,
            search_results=self._all_results,
            row_indices=self._row_indices,
        )
        self._context_preview.setPlainText(self._render_context_preview())

    def _update_token_label(self) -> None:
        """Refresh the ~token estimate and optional over-limit warning."""
        if self._token_label is None:
            return
        n = len(self._row_indices)
        tok = estimate_tokens(self._context)
        self._token_label.setText(f"~{tok:,} tokens  ({n} result{'s' if n != 1 else ''} selected)")
        if self._warn_label is not None:
            if n > LLM_CONTEXT_WARN:
                self._warn_label.setText(
                    f"⚠ {n} results selected — large prompts may be slow or exceed the model's context window."
                )
                self._warn_label.setVisible(True)
            elif n > LLM_CONTEXT_MAX:
                self._warn_label.setText(
                    f"⚠ {n} results selected — default is {LLM_CONTEXT_MAX}.  Consider reducing to keep prompts small."
                )
                self._warn_label.setVisible(True)
            else:
                self._warn_label.setVisible(False)

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

        self._append_question(prompt)
        self._send_btn.setEnabled(False)
        self._busy_bar.setVisible(True)

        # Parent the worker to the dialog so it will be cleaned up with it.
        self._worker = _SearchAIWorker(provider, messages, parent=self)
        self._worker.chunk.connect(self._on_chunk)
        self._worker.done.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        # Ensure we clear our reference and delete the thread object when finished
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_finished(self) -> None:
        # Called in the GUI thread when the QThread object has finished.
        try:
            if self._worker is not None:
                self._worker.deleteLater()
        finally:
            self._worker = None

    def _on_chunk(self, text: str) -> None:
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
        cursor.insertText(text, fmt)
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()

    def _on_done(self) -> None:
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        # Separator between turns
        cursor.insertHtml('<hr style="border: 0; border-top: 1px solid #444; margin: 6px 0;"><br>')
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()
        self._busy_bar.setVisible(False)
        self._send_btn.setEnabled(True)

    def _on_error(self, msg: str) -> None:
        self._append_error(msg)
        self._busy_bar.setVisible(False)
        self._send_btn.setEnabled(True)

    def _append_question(self, prompt: str) -> None:
        """Insert a colour-coded user question block followed by the AI label."""
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        safe_prompt = html.escape(prompt).replace("\n", "<br>")
        cursor.insertHtml(
            '<span style="color: #4a9eff; font-weight: bold;">You:</span><br>'
            f'<span style="color: #cccccc;">{safe_prompt}</span><br><br>'
            '<span style="color: #7bc67e; font-weight: bold;">AI:</span><br>'
        )
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()

    def _clear_response(self) -> None:
        self._response_area.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _open_settings(self) -> None:
        """Launch the settings dialog so the user can configure the LLM provider."""
        from vector_inspector.ui.dialogs.settings_dialog import SettingsDialog

        dlg = SettingsDialog(self._app_state.settings_service, self)
        dlg.exec()

    def _get_provider(self) -> Any | None:
        try:
            return self._app_state.llm_provider
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
                self._configure_llm_btn.setVisible(not available)
            else:
                status = "No LLM provider configured — click 'Configure LLM…' to set one up"
                color = "#d9534f"
                self._configure_llm_btn.setVisible(True)
        except Exception:
            status = "Provider status unknown"
            color = "gray"
            self._configure_llm_btn.setVisible(False)
        self._status_label.setText(status)
        self._status_label.setStyleSheet(f"color: {color}; font-size: 11px;")

    def _append_error(self, msg: str) -> None:
        cursor = self._response_area.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        escaped_msg = html.escape(msg, quote=True)
        cursor.insertHtml(f'<span style="color: #d9534f;">[Error: {escaped_msg}]</span><br><br>')
        self._response_area.setTextCursor(cursor)
        self._response_area.ensureCursorVisible()
        full_msg = f"Ask the AI error: {msg}"
        log_error(full_msg)
        self._status_label.setText("Error — hover for details")
        self._status_label.setToolTip(html.escape(full_msg, quote=True))
        self._status_label.setStyleSheet("color: #d9534f; font-size: 11px;")

    def _render_context_preview(self) -> str:
        """Render a short plain-text summary of the attached context."""
        ctx = self._context
        lines = [f"Search input: {ctx.get('search_input', '')!r}"]
        top = ctx.get("top_results", [])
        if top:
            lines.append(f"Top {len(top)} result(s) attached:")
            for item in top[:3]:
                dist = f"{item['distance']:.4f}" if item["distance"] is not None else "N/A"
                lines.append(f"  #{item['rank']} id={item['id']!r}  distance={dist}")
            if len(top) > 3:
                lines.append(f"  … and {len(top) - 3} more")
        selected = ctx.get("selected_result")
        if selected:
            dist = f"{selected['distance']:.4f}" if selected["distance"] is not None else "N/A"
            lines.append(f"Selected: #{selected['rank']} id={selected['id']!r}  distance={dist}")
        return "\n".join(lines)
