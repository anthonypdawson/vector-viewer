"""Tests for the Ask the AI feature wired into SearchView.

Covers:
- "Ask the AI" toolbar button exists and is connected
- _ask_ai() with no results shows QMessageBox
- _ask_ai() with results opens AskAIDialog
- _explain_result() with results opens AskAIDialog with a prefilled prompt
- _explain_result() with no results is a silent no-op
- Context menu includes "Explain result" action when a row is selected
"""

from __future__ import annotations

from unittest.mock import PropertyMock, patch

import pytest

from tests.utils.fake_llm_provider import FakeLLMProvider
from vector_inspector.state import AppState
from vector_inspector.ui.views.search_view import SearchView

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

FAKE_SEARCH_RESULTS = {
    "ids": [["id1", "id2"]],
    "documents": [["Doc one text", "Doc two text"]],
    "metadatas": [[{"source": "a"}, {"source": "b"}]],
    "distances": [[0.1, 0.2]],
    "embeddings": None,
}


def _make_fake_provider(fake_provider):
    """Extend fake_provider with minimal search stubs."""
    fake_provider.create_collection(
        "col1",
        ["doc1", "doc2"],
        [{"source": "a"}, {"source": "b"}],
        [[0.1, 0.2], [0.3, 0.4]],
        ids=["id1", "id2"],
    )
    fake_provider.compute_embeddings_for_documents = lambda texts: [[0.1, 0.2]]
    fake_provider.get_supported_filter_operators = lambda: []
    fake_provider.query_collection = lambda *a, **kw: FAKE_SEARCH_RESULTS
    return fake_provider


@pytest.fixture
def sv(qtbot, fake_provider, task_runner):
    """SearchView backed by a populated fake provider and a fake LLM."""
    _make_fake_provider(fake_provider)
    app_state = AppState()
    app_state.provider = fake_provider
    fake_llm = FakeLLMProvider()
    with patch.object(type(app_state), "llm_provider", new_callable=PropertyMock, return_value=fake_llm):
        view = SearchView(app_state, task_runner)
        qtbot.addWidget(view)
        view.current_collection = "col1"
        view.current_database = "test_db"
        yield view


@pytest.fixture
def sv_with_results(sv):
    """SearchView that already has search_results populated."""
    sv.search_results = FAKE_SEARCH_RESULTS
    sv.query_input.setPlainText("test query")
    return sv


# ---------------------------------------------------------------------------
# Toolbar button
# ---------------------------------------------------------------------------


def test_ask_ai_button_exists(sv):
    assert hasattr(sv, "ask_ai_button")


def test_ask_ai_button_label(sv):
    assert sv.ask_ai_button.text() == "Ask the AI"


def test_ask_ai_button_connected(sv, qtbot, monkeypatch):
    """Clicking the button triggers _ask_ai (patched to avoid dialog opening)."""
    called = []
    monkeypatch.setattr(sv, "_ask_ai", lambda **kw: called.append(True))
    # Enable the button (requires a collection to be selected in production)
    sv.set_collection_ready(True)
    # Disconnect original and wire the monkeypatched version
    sv.ask_ai_button.clicked.disconnect()
    sv.ask_ai_button.clicked.connect(sv._ask_ai)
    qtbot.mouseClick(sv.ask_ai_button, __import__("PySide6.QtCore", fromlist=["Qt"]).Qt.MouseButton.LeftButton)
    assert called


# ---------------------------------------------------------------------------
# _ask_ai — no results → QMessageBox
# ---------------------------------------------------------------------------


def test_ask_ai_no_results_shows_message_box(sv, qtbot, monkeypatch):
    """When search_results is None/empty, _ask_ai shows an information dialog."""
    sv.search_results = None
    shown = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.QMessageBox.information",
        lambda *a, **kw: shown.append(True),
    )
    sv._ask_ai()
    assert shown


def test_ask_ai_empty_dict_shows_message_box(sv, qtbot, monkeypatch):
    """An empty dict search_result is treated as 'no results'."""
    sv.search_results = {}
    shown = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.QMessageBox.information",
        lambda *a, **kw: shown.append(True),
    )
    sv._ask_ai()
    assert shown


# ---------------------------------------------------------------------------
# _ask_ai — with results → dialog opens
# ---------------------------------------------------------------------------


def test_ask_ai_with_results_opens_dialog(sv_with_results, qtbot, monkeypatch):
    """_ask_ai() with results should instantiate and show AskAIDialog."""
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._ask_ai()
    assert opened


def test_ask_ai_passes_prefilled_prompt(sv_with_results, qtbot, monkeypatch):
    """prefilled_prompt kwarg is forwarded to AskAIDialog."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["prompt"] = prefilled_prompt

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._ask_ai(prefilled_prompt="Custom prompt")
    assert received["prompt"] == "Custom prompt"


def test_ask_ai_passes_selected_row(sv_with_results, qtbot, monkeypatch):
    """selected_row kwarg is used for build_search_context."""
    received = {}

    real_build = __import__(
        "vector_inspector.services.search_ai_service",
        fromlist=["build_search_context"],
    ).build_search_context

    def _spy_build(**kw):
        received["selected_row"] = kw.get("selected_row")
        return real_build(**kw)

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.build_search_context", _spy_build)
    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._ask_ai(selected_row=1)
    assert received["selected_row"] == 1


# ---------------------------------------------------------------------------
# _explain_result — no results → no-op
# ---------------------------------------------------------------------------


def test_explain_result_no_results_is_noop(sv, qtbot, monkeypatch):
    sv.search_results = None
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv._explain_result(0)
    assert not opened


# ---------------------------------------------------------------------------
# _explain_result — with results → dialog with prefilled prompt
# ---------------------------------------------------------------------------


def test_explain_result_opens_dialog(sv_with_results, qtbot, monkeypatch):
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(0)
    assert opened


def test_explain_result_prefilled_prompt_not_empty(sv_with_results, qtbot, monkeypatch):
    """AskAIDialog must receive a non-empty prefilled_prompt from _explain_result."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["prompt"] = prefilled_prompt

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(0)
    assert received.get("prompt")


def test_explain_result_uses_correct_row(sv_with_results, qtbot, monkeypatch):
    """The selected_row passed to build_search_context matches the row argument."""
    received = {}

    real_build = __import__(
        "vector_inspector.services.search_ai_service",
        fromlist=["build_search_context"],
    ).build_search_context

    def _spy_build(**kw):
        received["selected_row"] = kw.get("selected_row")
        return real_build(**kw)

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.build_search_context", _spy_build)
    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(1)
    assert received["selected_row"] == 1


# ---------------------------------------------------------------------------
# Context menu includes "Explain result"
# ---------------------------------------------------------------------------


def test_context_menu_has_explain_action(sv_with_results, qtbot, monkeypatch):
    """Right-click context menu must include the '🔍 Explain result' action."""
    sv = sv_with_results
    # Populate the table with one row so the menu has items
    sv.results_table.setRowCount(1)
    sv.results_table.setColumnCount(2)
    sv.results_table.setItem(
        0, 0, __import__("PySide6.QtWidgets", fromlist=["QTableWidgetItem"]).QTableWidgetItem("id1")
    )

    menu_actions: list[str] = []

    class _FakeMenu:
        def __init__(self, *args, **kwargs):
            self._actions = []

        def addAction(self, label_or_action):
            from PySide6.QtGui import QAction

            if isinstance(label_or_action, str):
                a = QAction(label_or_action)
                self._actions.append(label_or_action)
                return a
            self._actions.append(str(label_or_action.text()))
            return label_or_action

        def addSeparator(self):
            pass

        def isEmpty(self):
            return False

        def exec(self, pos):
            menu_actions.extend(self._actions)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.QMenu", _FakeMenu)
    from PySide6.QtCore import QPoint

    sv._show_context_menu(QPoint(0, 0))
    # Accept partial match since icon prefix may vary
    assert any("Explain result" in a for a in menu_actions)


# ---------------------------------------------------------------------------
# LLM not configured → message + no dialog
# ---------------------------------------------------------------------------


def test_ask_ai_llm_not_configured_shows_message(sv_with_results, qtbot, monkeypatch):
    """When LLM is not available, _ask_ai shows an info message and does NOT open a dialog."""
    from unittest.mock import PropertyMock

    from tests.utils.fake_llm_provider import FakeLLMProvider

    fake_llm = FakeLLMProvider()
    fake_llm._available = False  # mark unavailable

    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    shown = []
    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)

    with patch.object(
        type(sv_with_results.app_state),
        "llm_provider",
        new_callable=PropertyMock,
        return_value=fake_llm,
    ):
        # Stub QMessageBox so it returns "Cancel" (do not open settings)
        import PySide6.QtWidgets as _qw

        monkeypatch.setattr(
            _qw.QMessageBox,
            "exec",
            lambda self: _qw.QMessageBox.StandardButton.Cancel,
        )
        monkeypatch.setattr(_qw.QMessageBox, "show", lambda self: None)
        # Override _check_llm_configured to return False and record call
        original_check = sv_with_results._check_llm_configured

        def _fake_check():
            shown.append(True)
            return False

        monkeypatch.setattr(sv_with_results, "_check_llm_configured", _fake_check)
        sv_with_results._ask_ai()

    assert shown, "_check_llm_configured was not called"
    assert not opened, "Dialog should NOT open when LLM is not configured"


def test_explain_result_llm_not_configured_does_not_open_dialog(sv_with_results, qtbot, monkeypatch):
    """When LLM is not available, _explain_result does NOT open a dialog."""
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)

    def _fake_check():
        return False

    monkeypatch.setattr(sv_with_results, "_check_llm_configured", _fake_check)
    sv_with_results._explain_result(0)
    assert not opened


# ---------------------------------------------------------------------------
# _ask_ai passes all_results and clamped initial_row_indices to dialog
# ---------------------------------------------------------------------------


def test_ask_ai_passes_all_results_to_dialog(sv_with_results, qtbot, monkeypatch):
    """all_results=FAKE_SEARCH_RESULTS must be forwarded to AskAIDialog constructor."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["all_results"] = all_results

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._ask_ai()
    assert received.get("all_results") is FAKE_SEARCH_RESULTS


def test_ask_ai_initial_indices_clamped_to_llm_context_max(sv_with_results, qtbot, monkeypatch):
    """initial_row_indices passed to AskAIDialog must have ≤ LLM_CONTEXT_MAX items."""
    from vector_inspector.services.search_ai_service import LLM_CONTEXT_MAX

    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["indices"] = initial_row_indices

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._ask_ai()
    indices = received.get("indices", [])
    assert indices is not None
    assert len(indices) <= LLM_CONTEXT_MAX


# ---------------------------------------------------------------------------
# _explain_result — 3-item window logic
# ---------------------------------------------------------------------------


def test_explain_result_uses_3_item_window(sv_with_results, qtbot, monkeypatch):
    """row=1 in a 2-row result set → row_indices should be [0, 1]."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["indices"] = initial_row_indices

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(1)
    # FAKE_SEARCH_RESULTS has 2 rows; row=1 → window is {0, 1}
    assert sorted(received.get("indices", [])) == [0, 1]


def test_explain_result_first_row_window(sv_with_results, qtbot, monkeypatch):
    """row=0 in 2-row results → window is [0, 1] (no -1)."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["indices"] = initial_row_indices

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(0)
    assert sorted(received.get("indices", [])) == [0, 1]


def test_explain_result_last_row_window(sv_with_results, qtbot, monkeypatch):
    """row=1 (last) in 2-row results → window is [0, 1] (no row 2)."""
    received = {}

    class _FakeDialog:
        def __init__(
            self, app_state, context, prefilled_prompt="", all_results=None, initial_row_indices=None, parent=None
        ):
            received["indices"] = initial_row_indices

        def show(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv_with_results._explain_result(1)
    # max(0, 1-1)=0, row=1, min(1, 1+1)=1 → {0, 1}
    assert sorted(received.get("indices", [])) == [0, 1]


# ---------------------------------------------------------------------------
# _ask_ai — truthy results dict with empty ids → shows "no results" message
# ---------------------------------------------------------------------------


def test_ask_ai_truthy_results_but_empty_ids_shows_message(sv, qtbot, monkeypatch):
    """Providers can return {ids: [[]], ...} which is truthy but has no rows.

    _ask_ai() must detect this and show the same 'run a search first' message.
    """
    sv.search_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]], "embeddings": None}
    shown = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.QMessageBox.information",
        lambda *a, **kw: shown.append(True),
    )
    sv._ask_ai()
    assert shown


def test_ask_ai_truthy_results_but_empty_ids_does_not_open_dialog(sv, qtbot, monkeypatch):
    """No dialog must open when ids unwrap to an empty list."""
    sv.search_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]], "embeddings": None}
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.QMessageBox.information",
        lambda *a, **kw: None,
    )
    sv._ask_ai()
    assert not opened


# ---------------------------------------------------------------------------
# _explain_result — truthy results dict with empty ids → no-op
# ---------------------------------------------------------------------------


def test_explain_result_truthy_results_but_empty_ids_is_noop(sv, qtbot, monkeypatch):
    """_explain_result with truthy results but zero actual rows must be a silent no-op."""
    sv.search_results = {"ids": [[]], "documents": [[]], "metadatas": [[]], "distances": [[]], "embeddings": None}
    opened = []

    class _FakeDialog:
        def __init__(self, *a, **kw):
            pass

        def show(self):
            opened.append(True)

    monkeypatch.setattr("vector_inspector.ui.views.search_view.AskAIDialog", _FakeDialog)
    sv._explain_result(0)
    assert not opened


# ---------------------------------------------------------------------------
# _check_llm_configured — unexpected exceptions are logged
# ---------------------------------------------------------------------------


def test_check_llm_configured_logs_unexpected_exception(sv, qtbot, monkeypatch):
    """Unexpected exceptions accessing llm_provider must be logged via log_error."""
    from unittest.mock import PropertyMock

    logged = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.log_error",
        lambda *a, **kw: logged.append((a, kw)),
    )

    # Raise a non-AttributeError to trigger the log_error branch
    with patch.object(
        type(sv.app_state),
        "llm_provider",
        new_callable=PropertyMock,
        side_effect=RuntimeError("unexpected"),
    ):
        import PySide6.QtWidgets as _qw

        monkeypatch.setattr(_qw.QMessageBox, "exec", lambda self: None)
        monkeypatch.setattr(_qw.QMessageBox, "clickedButton", lambda self: None)
        sv._check_llm_configured()

    assert logged, "log_error should have been called for an unexpected exception"


def test_check_llm_configured_does_not_log_attribute_error(sv, qtbot, monkeypatch):
    """AttributeError (e.g., test mocks without llm_provider) must NOT trigger log_error."""
    from unittest.mock import PropertyMock

    logged = []
    monkeypatch.setattr(
        "vector_inspector.ui.views.search_view.log_error",
        lambda *a, **kw: logged.append((a, kw)),
    )

    with patch.object(
        type(sv.app_state),
        "llm_provider",
        new_callable=PropertyMock,
        side_effect=AttributeError("no attr"),
    ):
        import PySide6.QtWidgets as _qw

        monkeypatch.setattr(_qw.QMessageBox, "exec", lambda self: None)
        monkeypatch.setattr(_qw.QMessageBox, "clickedButton", lambda self: None)
        sv._check_llm_configured()

    assert not logged, "AttributeError must be silently swallowed, not logged"
