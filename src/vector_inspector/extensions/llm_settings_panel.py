"""LLM provider configuration panel for the Settings dialog.

NOTE (temporary): The full LLM configuration UI is included in Vector
Inspector to make local verification and developer testing
straightforward. The intended long-term design is for Vector Studio to
inject the full configuration panel via the `settings_panel_hook` while
Vector Inspector (free tier) exposes only a small status group and a
disabled "Configure LLM…" stub. This file is therefore a temporary placement
for the UI and will be migrated into the Vector Studio extension in a
follow-up change.

This panel is registered automatically via ``settings_panel_hook`` when
``vector_inspector.extensions`` is imported.  It renders the provider
selector, connection fields, and a live health-check button inline — no
separate dialog required.

For providers that expose a model list (ollama, openai-compatible) the model
field is an editable combo box populated via a background thread.  llama-cpp
uses a plain text field because the model is a local file path.

Context length and temperature fields are present but disabled in the free
tier; Vector Studio enables and wires them.
"""

from __future__ import annotations

import html
from datetime import UTC

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from vector_inspector.core.logging import log_error, log_info
from vector_inspector.extensions import settings_panel_hook

_PROVIDERS = ["auto", "ollama", "openai-compatible", "llama-cpp"]
_PROVIDER_INDEX = {p: i for i, p in enumerate(_PROVIDERS)}


class _HealthCheckThread(QThread):
    """Background thread to probe LLM provider health via ``get_health()``."""

    health_ready = Signal(object)  # emits HealthResult or None

    def __init__(self, settings, parent=None) -> None:
        super().__init__(parent)
        self._settings = settings

    def run(self) -> None:
        try:
            from vector_inspector.core.llm_providers import LLMProviderFactory

            provider = LLMProviderFactory.create_from_settings(self._settings)
            if provider is None:
                self.health_ready.emit(None)
                return
            self.health_ready.emit(provider.get_health())
        except Exception as exc:
            import uuid
            from datetime import datetime

            from vector_inspector.core.llm_providers.types import HealthResult

            # Log full exception with traceback for developers (redact externally as needed)
            try:
                log_error("LLM health check failed (id=%s): %s", uuid.uuid4().hex[:8], exc, exc_info=True)
            except Exception:
                # Best-effort logging; don't raise from the health thread
                pass

            # Emit a short, sanitized remediation hint (<=200 chars) with a correlation id
            cid = uuid.uuid4().hex[:8]
            hint = f"Health check failed (id: {cid}) — see application logs for details"
            hint = hint[:200]
            self.health_ready.emit(
                HealthResult(
                    ok=False,
                    provider="error",
                    models=[],
                    version=None,
                    last_checked=datetime.now(UTC).isoformat(),
                    retryable=False,
                    remediation_hint=hint,
                )
            )


class _ModelListThread(QThread):
    """Background thread that fetches available models for a provider."""

    models_ready = Signal(list)  # list[str] — may be empty on failure
    error = Signal(str)

    def __init__(self, provider_name: str, url: str, api_key: str, parent=None) -> None:
        super().__init__(parent)
        self._provider_name = provider_name
        self._url = url
        self._api_key = api_key

    def run(self) -> None:
        try:
            if self._provider_name == "ollama":
                from vector_inspector.core.llm_providers.ollama_provider import OllamaProvider

                provider = OllamaProvider(base_url=self._url)
            elif self._provider_name == "openai-compatible":
                from vector_inspector.core.llm_providers.openai_compatible_provider import OpenAICompatibleProvider

                provider = OpenAICompatibleProvider(base_url=self._url, model="", api_key=self._api_key)
            else:
                self.models_ready.emit([])
                return
            names = [m.model_name for m in provider.list_models()]
            self.models_ready.emit(names)
        except Exception as exc:
            self.error.emit(str(exc))


# ---------------------------------------------------------------------------
# Hook handler — renders inline, no secondary dialog
# ---------------------------------------------------------------------------


def _make_model_combo(saved_model: str) -> tuple[QComboBox, QPushButton]:
    """Return an editable model combo and its companion refresh button."""
    combo = QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
    if saved_model:
        combo.addItem(saved_model)
        combo.setCurrentText(saved_model)
    else:
        combo.setPlaceholderText("Select or type model…")
    refresh_btn = QPushButton("↺")
    refresh_btn.setFixedWidth(28)
    refresh_btn.setToolTip("Refresh model list")
    return combo, refresh_btn


def _add_llm_status_section(parent_layout, settings_service, _dialog=None) -> None:
    """Hook handler: adds the LLM Provider configuration group to the settings dialog."""
    group = QGroupBox("LLM Provider")
    group.setObjectName("llm_status_group")
    form = QFormLayout()
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

    # --- Provider selector ---
    provider_combo = QComboBox()
    provider_combo.setObjectName("llm_provider_combo")
    provider_combo.addItems(_PROVIDERS)
    provider_combo.setCurrentIndex(_PROVIDER_INDEX.get(settings_service.get_llm_provider(), 0))
    form.addRow("Provider:", provider_combo)

    # --- Stacked provider-specific fields ---
    stack = QStackedWidget()
    stack.setObjectName("llm_stack")

    # 0: auto
    auto_page = QWidget()
    auto_layout = QVBoxLayout(auto_page)
    auto_layout.setContentsMargins(0, 2, 0, 2)
    auto_layout.addWidget(
        QLabel("Tries providers in order: ollama → llama-cpp. Does not auto-detect openai-compatible.")
    )
    stack.addWidget(auto_page)

    # 1: ollama
    ollama_page = QWidget()
    ollama_form = QFormLayout(ollama_page)
    ollama_url = QLineEdit(settings_service.get_llm_ollama_url())
    ollama_url.setObjectName("llm_ollama_url")
    ollama_url.setPlaceholderText("http://localhost:11434")
    ollama_model, ollama_refresh_btn = _make_model_combo(settings_service.get_llm_ollama_model())
    ollama_model.setObjectName("llm_ollama_model")
    ollama_model_row = QHBoxLayout()
    ollama_model_row.addWidget(ollama_model)
    ollama_model_row.addWidget(ollama_refresh_btn)
    ollama_form.addRow("URL:", ollama_url)
    ollama_form.addRow("Model:", ollama_model_row)
    stack.addWidget(ollama_page)

    # 2: openai-compatible
    openai_page = QWidget()
    openai_form = QFormLayout(openai_page)
    openai_url = QLineEdit(settings_service.get_llm_openai_url())
    openai_url.setObjectName("llm_openai_url")
    openai_url.setPlaceholderText("https://api.openai.com/v1")
    openai_key = QLineEdit(settings_service.get_llm_openai_api_key())
    openai_key.setObjectName("llm_openai_key")
    openai_key.setEchoMode(QLineEdit.EchoMode.Password)
    openai_key.setPlaceholderText("sk-…")
    openai_key.setMaximumWidth(200)
    openai_model, openai_refresh_btn = _make_model_combo(settings_service.get_llm_openai_model())
    openai_model.setObjectName("llm_openai_model")
    openai_model_row = QHBoxLayout()
    openai_model_row.addWidget(openai_model)
    openai_model_row.addWidget(openai_refresh_btn)
    openai_form.addRow("Base URL:", openai_url)
    openai_form.addRow("API Key:", openai_key)
    openai_form.addRow("Model:", openai_model_row)
    stack.addWidget(openai_page)

    # 3: llama-cpp (file path — no model list)
    llamacpp_page = QWidget()
    llamacpp_form = QFormLayout(llamacpp_page)
    llamacpp_path = QLineEdit(settings_service.get_llm_model_path())
    llamacpp_path.setObjectName("llm_llamacpp_path")
    llamacpp_path.setPlaceholderText("/path/to/model.gguf")
    llamacpp_browse_btn = QPushButton("Browse…")
    llamacpp_browse_btn.setObjectName("llm_llamacpp_browse_btn")
    llamacpp_path_row = QHBoxLayout()
    llamacpp_path_row.addWidget(llamacpp_path)
    llamacpp_path_row.addWidget(llamacpp_browse_btn)
    llamacpp_form.addRow("Model path:", llamacpp_path_row)
    download_btn = QPushButton("Download default model (Phi-3-mini)…")
    download_btn.setObjectName("llm_download_btn")
    download_btn.setEnabled(False)
    download_btn.setToolTip("Requires Vector Studio")
    download_status_label = QLabel("")
    download_status_label.setObjectName("llm_download_status")
    download_btn_row = QHBoxLayout()
    download_btn_row.addWidget(download_btn)
    download_btn_row.addWidget(download_status_label)
    download_btn_row.addStretch()
    llamacpp_form.addRow(download_btn_row)
    stack.addWidget(llamacpp_page)

    stack.setCurrentIndex(_PROVIDER_INDEX.get(settings_service.get_llm_provider(), 0))
    form.addRow(stack)

    # --- Advanced fields (Vector Studio enables these) ---
    ctx_spin = QSpinBox()
    ctx_spin.setObjectName("llm_context_length")
    ctx_spin.setRange(512, 131072)
    ctx_spin.setSingleStep(512)
    ctx_spin.setValue(settings_service.get_llm_context_length())
    ctx_spin.setEnabled(False)
    ctx_spin.setToolTip("Requires Vector Studio")
    form.addRow("Context length:", ctx_spin)

    temp_spin = QDoubleSpinBox()
    temp_spin.setObjectName("llm_temperature")
    temp_spin.setRange(0.0, 2.0)
    temp_spin.setSingleStep(0.05)
    temp_spin.setDecimals(2)
    temp_spin.setValue(settings_service.get_llm_temperature())
    temp_spin.setEnabled(False)
    temp_spin.setToolTip("Requires Vector Studio")
    form.addRow("Temperature:", temp_spin)

    # --- Test Connection row ---
    status_label = QLabel("Not checked")
    status_label.setWordWrap(False)
    status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    # Use plain-text rendering to avoid interpreting user/remote content as HTML.
    status_label.setTextFormat(Qt.TextFormat.PlainText)
    # Increase max width so messages have more room, but still cap it to avoid
    # unbounded window growth. This is ~double the previous value.
    status_label.setMaximumWidth(1600)
    # Ensure the full status/error text is available on hover.
    status_label.setToolTip("Not checked")
    status_label.setObjectName("llm_status_label")
    test_btn = QPushButton("Test Connection")
    test_btn.setObjectName("llm_check_btn")
    test_row = QHBoxLayout()
    test_row.addWidget(status_label)
    test_row.addStretch()
    test_row.addWidget(test_btn)
    form.addRow(test_row)

    group.setLayout(form)
    parent_layout.addWidget(group)

    # --- Auto-save wiring ---
    provider_combo.currentTextChanged.connect(
        lambda text: (
            settings_service.set_llm_provider(text),
            stack.setCurrentIndex(_PROVIDER_INDEX.get(text, 0)),
        )
    )
    ollama_url.editingFinished.connect(lambda: settings_service.set_llm_ollama_url(ollama_url.text().strip()))
    ollama_model.currentTextChanged.connect(
        lambda text: settings_service.set_llm_ollama_model(text.strip()) if text.strip() else None
    )
    openai_url.editingFinished.connect(lambda: settings_service.set_llm_openai_url(openai_url.text().strip()))
    openai_key.editingFinished.connect(lambda: settings_service.set_llm_openai_api_key(openai_key.text()))
    openai_model.currentTextChanged.connect(
        lambda text: settings_service.set_llm_openai_model(text.strip()) if text.strip() else None
    )
    llamacpp_path.editingFinished.connect(lambda: settings_service.set_llm_model_path(llamacpp_path.text().strip()))

    def _on_browse_clicked() -> None:
        from PySide6.QtWidgets import QFileDialog

        path, _ = QFileDialog.getOpenFileName(
            group,
            "Select GGUF Model File",
            settings_service.get_llm_model_path() or "",
            "GGUF Models (*.gguf);;All Files (*)",
        )
        if path:
            llamacpp_path.setText(path)
            settings_service.set_llm_model_path(path)

    llamacpp_browse_btn.clicked.connect(_on_browse_clicked)

    # --- Model list loading ---
    _model_threads: list[_ModelListThread] = []

    def _load_models(provider_name: str, url: str, api_key: str, combo: QComboBox, refresh_btn: QPushButton) -> None:
        refresh_btn.setEnabled(False)
        refresh_btn.setText("…")
        saved = combo.currentText()
        thread = _ModelListThread(provider_name, url, api_key, parent=group)

        def _on_models(names: list[str]) -> None:
            current = combo.currentText()
            combo.blockSignals(True)
            combo.clear()
            combo.addItems(names)
            # keep the previously selected/typed value even if it's not in the list
            if current and current not in names:
                combo.insertItem(0, current)
            target = current or saved
            if target:
                combo.setCurrentText(target)
            combo.blockSignals(False)
            refresh_btn.setText("↺")
            refresh_btn.setEnabled(True)
            if thread in _model_threads:
                _model_threads.remove(thread)

        def _on_error(_msg: str) -> None:
            refresh_btn.setText("↺")
            refresh_btn.setEnabled(True)
            if thread in _model_threads:
                _model_threads.remove(thread)

        thread.models_ready.connect(_on_models)
        thread.error.connect(_on_error)
        _model_threads.append(thread)
        thread.start()

    def _refresh_ollama() -> None:
        _load_models(
            "ollama", ollama_url.text().strip() or "http://localhost:11434", "", ollama_model, ollama_refresh_btn
        )

    def _refresh_openai() -> None:
        _load_models(
            "openai-compatible", openai_url.text().strip(), openai_key.text(), openai_model, openai_refresh_btn
        )

    ollama_refresh_btn.clicked.connect(_refresh_ollama)
    openai_refresh_btn.clicked.connect(_refresh_openai)

    # Auto-load when the page is first shown
    def _on_stack_changed(index: int) -> None:
        if index == 1:  # ollama
            _refresh_ollama()
        elif index == 2:  # openai-compatible
            _refresh_openai()

    stack.currentChanged.connect(_on_stack_changed)
    # Trigger for the initially visible page
    _on_stack_changed(stack.currentIndex())

    # Reload model list when URL/key change
    ollama_url.editingFinished.connect(_refresh_ollama)
    openai_url.editingFinished.connect(_refresh_openai)
    openai_key.editingFinished.connect(_refresh_openai)

    # --- Health check ---
    _thread_holder: list[_HealthCheckThread] = []

    def _on_test_clicked() -> None:
        test_btn.setEnabled(False)
        status_label.setText("Checking…")
        thread = _HealthCheckThread(settings_service, parent=group)

        def _on_health(result) -> None:
            # Build a concise, plain-text visible label and put full
            # diagnostics in the tooltip (HTML-escaped to avoid markup
            # interpretation). Color is applied via stylesheet.
            if result is None:
                short = "No provider configured — hover for details"
                tooltip = "No provider configured"
                status_label.setStyleSheet("color: #d9534f")
                log_info("LLM health check: no provider configured")
            elif result.ok:
                models_full = ", ".join(result.models) if result.models else "—"
                model_count = len(result.models) if result.models else 0
                version_str = f" v{result.version}" if result.version else ""
                models_text = f"{model_count} model{'s' if model_count != 1 else ''}" if model_count else "—"
                short = f"OK — {result.provider}{version_str} ({models_text})"
                tooltip = f"OK — {result.provider}{version_str} ({models_full})"
                status_label.setStyleSheet("color: #28a745")
            else:
                hint = f" — {result.remediation_hint}" if result.remediation_hint else ""
                short = "Unavailable — hover for details"
                tooltip = f"Unavailable{hint}"
                status_label.setStyleSheet("color: #d9534f")
                if result.remediation_hint:
                    log_error("LLM health check failed for %s: %s", result.provider, result.remediation_hint)

            # Escape the tooltip to prevent HTML injection and set plain text
            status_label.setText(short)
            status_label.setToolTip(html.escape(tooltip))
            test_btn.setEnabled(True)
            if thread in _thread_holder:
                _thread_holder.remove(thread)

        thread.health_ready.connect(_on_health)
        _thread_holder.append(thread)
        thread.start()

    test_btn.clicked.connect(_on_test_clicked)


settings_panel_hook.register(_add_llm_status_section)
