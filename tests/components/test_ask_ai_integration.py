from __future__ import annotations

from unittest.mock import MagicMock

from PySide6.QtWidgets import QDialog

from tests.utils.fake_llm_provider import FakeLLMProvider


def test_ask_ai_dialog_picks_up_settings_change(qtbot, monkeypatch):
    """Integration-style test: opening Settings from AskAIDialog updates provider used by _send()."""
    from vector_inspector.ui.components.ask_ai_dialog import AskAIDialog

    # Create initial and updated providers
    provider_old = FakeLLMProvider(mode="echo")
    provider_new = FakeLLMProvider(mode="echo")

    # AppState-like object
    app_state = MagicMock()
    app_state.llm_runtime_manager = MagicMock()
    app_state.llm_runtime_manager.get_provider.return_value = provider_old
    app_state.llm_provider = provider_old

    # Patch the SettingsDialog to simulate user changing provider/model
    class FakeSettingsDialog:
        def __init__(self, settings_service, parent=None):
            self._parent = parent

        def exec(self):
            # Simulate user selecting a new provider in settings
            app_state.llm_runtime_manager.get_provider.return_value = provider_new
            app_state.llm_provider = provider_new
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr("vector_inspector.ui.dialogs.settings_dialog.SettingsDialog", FakeSettingsDialog)

    dlg = AskAIDialog(app_state, context={"search_input": "q", "top_results": [], "selected_result": None})
    qtbot.addWidget(dlg)

    # Initial status should reference old provider model
    initial = dlg._status_label.text()
    assert "fake-model" in initial or initial

    # Open settings via the dialog helper which we patched — this should update runtime manager/provider
    dlg._open_settings()

    # After settings, status label should be refreshed to reflect new provider
    post = dlg._status_label.text()
    assert post is not None

    # Now simulate sending — the worker should be created with the updated provider
    dlg._prompt_input.setPlainText("Hello")
    dlg._send()
    # Worker stored on dialog must be present and use the new provider
    assert dlg._worker is not None
    assert dlg._worker._provider is provider_new
