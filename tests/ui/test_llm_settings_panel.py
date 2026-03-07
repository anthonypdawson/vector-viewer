"""Item 15 — UI tests for llm_settings_panel: model list loading, Test Connection, API key width."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QGroupBox, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

# ---------------------------------------------------------------------------
# Fake settings (no network calls when provider="auto")
# ---------------------------------------------------------------------------


class _FakeLLMSettings:
    def __init__(self):
        self._store: dict = {}

    def get_llm_provider(self):
        return "auto"

    def get_llm_ollama_url(self):
        return "http://localhost:11434"

    def get_llm_ollama_model(self):
        return "llama3.2"

    def get_llm_openai_url(self):
        return ""

    def get_llm_openai_api_key(self):
        return ""

    def get_llm_openai_model(self):
        return ""

    def get_llm_model_path(self):
        return ""

    def get_llm_context_length(self):
        return 4096

    def get_llm_temperature(self):
        return 0.1

    def get(self, key, default=None):
        return self._store.get(key, default)

    def set_llm_provider(self, v):
        self._store["llm.provider"] = v

    def set_llm_ollama_url(self, v):
        self._store["llm.ollama_url"] = v

    def set_llm_ollama_model(self, v):
        self._store["llm.ollama_model"] = v

    def set_llm_openai_url(self, v):
        self._store["llm.openai_url"] = v

    def set_llm_openai_api_key(self, v):
        self._store["llm.openai_api_key"] = v

    def set_llm_openai_model(self, v):
        self._store["llm.openai_model"] = v

    def set_llm_model_path(self, v):
        self._store["llm.model_path"] = v

    def set_llm_context_length(self, v):
        pass

    def set_llm_temperature(self, v):
        pass


def _build_panel(qtbot):
    """Construct the LLM settings panel and return (container, fake_settings)."""
    from vector_inspector.extensions.llm_settings_panel import _add_llm_status_section

    fake_settings = _FakeLLMSettings()
    container = QWidget()
    layout = QVBoxLayout(container)
    qtbot.addWidget(container)
    _add_llm_status_section(layout, fake_settings)
    return container, fake_settings


# ---------------------------------------------------------------------------
# Widget structure
# ---------------------------------------------------------------------------


class TestLLMSettingsPanelStructure:
    def test_group_box_created(self, qtbot):
        container, _ = _build_panel(qtbot)
        group = container.findChild(QGroupBox, "llm_status_group")
        assert group is not None

    def test_provider_combo_present_with_all_options(self, qtbot):
        from PySide6.QtWidgets import QComboBox

        container, _ = _build_panel(qtbot)
        combo = container.findChild(QComboBox, "llm_provider_combo")
        assert combo is not None
        texts = [combo.itemText(i) for i in range(combo.count())]
        assert "auto" in texts
        assert "ollama" in texts
        assert "openai-compatible" in texts
        assert "llama-cpp" in texts

    def test_test_connection_button_present_and_enabled(self, qtbot):
        container, _ = _build_panel(qtbot)
        btn = container.findChild(QPushButton, "llm_check_btn")
        assert btn is not None
        assert btn.isEnabled()

    def test_status_label_initial_text(self, qtbot):
        container, _ = _build_panel(qtbot)
        label = container.findChild(QLabel, "llm_status_label")
        assert label is not None
        assert label.text() == "Not checked"

    def test_download_button_disabled_premium_stub(self, qtbot):
        container, _ = _build_panel(qtbot)
        btn = container.findChild(QPushButton, "llm_download_btn")
        assert btn is not None
        assert not btn.isEnabled()
        assert "Vector Studio" in btn.toolTip()

    def test_advanced_fields_disabled_premium_stubs(self, qtbot):
        from PySide6.QtWidgets import QDoubleSpinBox, QSpinBox

        container, _ = _build_panel(qtbot)
        ctx = container.findChild(QSpinBox, "llm_context_length")
        temp = container.findChild(QDoubleSpinBox, "llm_temperature")
        assert ctx is not None and not ctx.isEnabled()
        assert temp is not None and not temp.isEnabled()
        assert "Vector Studio" in ctx.toolTip()
        assert "Vector Studio" in temp.toolTip()

    def test_openai_key_field_max_width_is_200(self, qtbot):
        """Item 15 — API key display width must not overflow the panel."""
        container, _ = _build_panel(qtbot)
        key_field = container.findChild(QLineEdit, "llm_openai_key")
        assert key_field is not None
        assert key_field.maximumWidth() == 200

    def test_openai_key_stores_full_value_despite_display_width(self, qtbot):
        """Item 15 — width constraint must not truncate the stored API key."""
        container, fake_settings = _build_panel(qtbot)
        key_field = container.findChild(QLineEdit, "llm_openai_key")
        long_key = "sk-" + "x" * 200
        # Prevent the panel from starting a real _ModelListThread during this
        # unit test (editingFinished triggers a model refresh). Patch the
        # thread class so `start()` is a no-op to avoid stray QThreads.
        with patch("vector_inspector.extensions.llm_settings_panel._ModelListThread") as MockThread:
            MockThread.return_value.start = MagicMock()
            key_field.setText(long_key)
            key_field.editingFinished.emit()
        assert fake_settings._store.get("llm.openai_api_key") == long_key


# ---------------------------------------------------------------------------
# Provider switching
# ---------------------------------------------------------------------------


class TestLLMSettingsPanelProviderSwitch:
    def test_switching_to_ollama_shows_stack_index_1(self, qtbot):
        from PySide6.QtWidgets import QComboBox, QStackedWidget

        container, _ = _build_panel(qtbot)
        stack = container.findChild(QStackedWidget, "llm_stack")
        combo = container.findChild(QComboBox, "llm_provider_combo")
        assert stack is not None and combo is not None

        with patch("vector_inspector.extensions.llm_settings_panel._ModelListThread") as MockThread:
            inst = MockThread.return_value
            inst.models_ready = MagicMock()
            inst.error = MagicMock()
            inst.models_ready.connect = MagicMock()
            inst.error.connect = MagicMock()
            inst.start = MagicMock()
            combo.setCurrentText("ollama")

        assert stack.currentIndex() == 1

    def test_switching_to_llama_cpp_shows_stack_index_3(self, qtbot):
        from PySide6.QtWidgets import QComboBox, QStackedWidget

        container, _ = _build_panel(qtbot)
        stack = container.findChild(QStackedWidget, "llm_stack")
        combo = container.findChild(QComboBox, "llm_provider_combo")

        with patch("vector_inspector.extensions.llm_settings_panel._ModelListThread") as MockThread:
            inst = MockThread.return_value
            inst.models_ready = MagicMock()
            inst.error = MagicMock()
            inst.models_ready.connect = MagicMock()
            inst.error.connect = MagicMock()
            inst.start = MagicMock()
            combo.setCurrentText("llama-cpp")

        assert stack.currentIndex() == 3

    def test_llama_cpp_path_field_present(self, qtbot):
        container, _ = _build_panel(qtbot)
        path_field = container.findChild(QLineEdit, "llm_llamacpp_path")
        assert path_field is not None


# ---------------------------------------------------------------------------
# Thread unit tests (run() called synchronously — no event loop required)
# ---------------------------------------------------------------------------


class TestHealthCheckThread:
    def _make_settings(self, provider="auto"):
        class _S:
            def get(self, key, default=None):
                if key == "llm.provider":
                    return provider
                return default

        return _S()

    def test_run_emits_health_result(self, qtbot):
        from vector_inspector.extensions.llm_settings_panel import _HealthCheckThread

        s = self._make_settings("auto")
        thread = _HealthCheckThread(s)
        results = []
        thread.health_ready.connect(lambda r: results.append(r))
        thread.run()
        assert len(results) == 1

    def test_run_emits_error_health_result_on_exception(self, qtbot):
        from vector_inspector.core.llm_providers import LLMProviderFactory
        from vector_inspector.extensions.llm_settings_panel import _HealthCheckThread

        s = self._make_settings("auto")
        thread = _HealthCheckThread(s)
        results = []
        thread.health_ready.connect(lambda r: results.append(r))
        with patch.object(LLMProviderFactory, "create_from_settings", side_effect=RuntimeError("boom")):
            thread.run()
        assert len(results) == 1
        assert results[0].ok is False
        assert results[0].provider == "error"


class TestModelListThread:
    def test_ollama_unreachable_emits_error(self, qtbot):
        from vector_inspector.extensions.llm_settings_panel import _ModelListThread

        thread = _ModelListThread("ollama", "http://127.0.0.1:19999", "", parent=None)
        model_results: list = []
        error_results: list = []
        thread.models_ready.connect(lambda m: model_results.append(m))
        thread.error.connect(lambda e: error_results.append(e))
        thread.run()
        # Either models_ready or error must fire exactly once
        assert len(model_results) + len(error_results) == 1

    def test_unknown_provider_emits_empty_list(self, qtbot):
        from vector_inspector.extensions.llm_settings_panel import _ModelListThread

        thread = _ModelListThread("unsupported", "", "", parent=None)
        results: list = []
        thread.models_ready.connect(lambda m: results.append(m))
        thread.run()
        assert results == [[]]

    def test_openai_emits_model_list_on_success(self, qtbot):
        from vector_inspector.extensions.llm_settings_panel import _ModelListThread

        fake_data = json.dumps({"data": [{"id": "gpt-4"}, {"id": "gpt-3.5-turbo"}]}).encode()
        mock_resp = MagicMock()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_resp.read.return_value = fake_data

        thread = _ModelListThread("openai-compatible", "http://localhost:1234", "sk-key", parent=None)
        results: list = []
        thread.models_ready.connect(lambda m: results.append(m))

        with patch("urllib.request.urlopen", return_value=mock_resp):
            thread.run()

        assert len(results) == 1
        assert "gpt-4" in results[0]
        assert "gpt-3.5-turbo" in results[0]
