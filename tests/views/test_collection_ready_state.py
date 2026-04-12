"""Tests for the 'collection ready' guard state across Data/Search/Visualization views.

Verifies that action buttons are disabled when no collection is selected and
enabled once a collection is provided, addressing the telemetry-derived bugs
around opening tabs/views with no active collection.
"""

import pytest

from vector_inspector.state import AppState
from vector_inspector.ui.views.metadata_view import MetadataView
from vector_inspector.ui.views.search_view import SearchView


# ---------------------------------------------------------------------------
# SearchView
# ---------------------------------------------------------------------------


@pytest.fixture
def sv_no_collection(qtbot, fake_provider, task_runner):
    app_state = AppState()
    # No provider/collection set
    view = SearchView(app_state, task_runner)
    qtbot.addWidget(view)
    return view


@pytest.fixture
def sv_with_provider(qtbot, fake_provider, task_runner):
    fake_provider.get_supported_filter_operators = lambda: []
    app_state = AppState()
    app_state.provider = fake_provider
    view = SearchView(app_state, task_runner)
    qtbot.addWidget(view)
    return view


def test_search_button_disabled_on_init(sv_no_collection):
    """Search button must start disabled when no collection is selected."""
    assert not sv_no_collection.search_button.isEnabled()


def test_ask_ai_button_disabled_on_init(sv_no_collection):
    """Ask AI button must start disabled when no collection is selected."""
    assert not sv_no_collection.ask_ai_button.isEnabled()


def test_search_status_shows_empty_state(sv_no_collection):
    """Status label shows 'Select a collection' when nothing is selected."""
    assert "collection" in sv_no_collection.results_status.text().lower()


def test_set_collection_ready_true_enables_buttons(sv_no_collection):
    """set_collection_ready(True) enables both action buttons."""
    sv_no_collection.set_collection_ready(True)
    assert sv_no_collection.search_button.isEnabled()
    assert sv_no_collection.ask_ai_button.isEnabled()


def test_set_collection_ready_false_disables_buttons(sv_with_provider):
    """set_collection_ready(False) disables both action buttons."""
    sv_with_provider.set_collection_ready(True)  # enable first
    sv_with_provider.set_collection_ready(False)
    assert not sv_with_provider.search_button.isEnabled()
    assert not sv_with_provider.ask_ai_button.isEnabled()


def test_set_collection_enables_buttons(sv_with_provider):
    """Calling set_collection() re-enables action buttons."""
    # Start disabled
    assert not sv_with_provider.search_button.isEnabled()
    sv_with_provider.current_collection = ""
    sv_with_provider.set_collection("test_collection", "db")
    assert sv_with_provider.search_button.isEnabled()
    assert sv_with_provider.ask_ai_button.isEnabled()


def test_collection_changed_signal_enables_buttons(sv_with_provider):
    """Emitting collection_changed enables buttons via _on_collection_changed."""
    sv_with_provider.app_state.database = "db"
    sv_with_provider.app_state.collection_changed.emit("test_collection")
    assert sv_with_provider.search_button.isEnabled()


def test_collection_changed_empty_disables_buttons(sv_with_provider):
    """Emitting collection_changed with empty string disables buttons."""
    sv_with_provider.set_collection_ready(True)  # enable first
    sv_with_provider.app_state.collection_changed.emit("")
    assert not sv_with_provider.search_button.isEnabled()


def test_provider_changed_disables_buttons(sv_with_provider):
    """Emitting provider_changed disables buttons (collection reset expected)."""
    sv_with_provider.set_collection_ready(True)
    sv_with_provider.app_state.provider_changed.emit(None)
    assert not sv_with_provider.search_button.isEnabled()


# ---------------------------------------------------------------------------
# MetadataView
# ---------------------------------------------------------------------------


@pytest.fixture
def mv_no_collection(qtbot, task_runner):
    app_state = AppState()
    view = MetadataView(app_state, task_runner)
    qtbot.addWidget(view)
    return view


def test_metadata_action_buttons_disabled_on_init(mv_no_collection):
    """MetadataView action buttons must be disabled at startup."""
    assert not mv_no_collection.action_buttons.isEnabled()


def test_metadata_set_collection_ready_true(mv_no_collection):
    """set_collection_ready(True) enables action buttons."""
    mv_no_collection.set_collection_ready(True)
    assert mv_no_collection.action_buttons.isEnabled()


def test_metadata_set_collection_ready_false(mv_no_collection):
    """set_collection_ready(False) disables action buttons."""
    mv_no_collection.set_collection_ready(True)
    mv_no_collection.set_collection_ready(False)
    assert not mv_no_collection.action_buttons.isEnabled()


def test_metadata_provider_changed_disables_buttons(qtbot, fake_provider, task_runner):
    """provider_changed signal disables action buttons (collection no longer valid)."""
    app_state = AppState()
    app_state.provider = fake_provider
    view = MetadataView(app_state, task_runner)
    qtbot.addWidget(view)
    view.set_collection_ready(True)  # pretend collection was selected
    view.app_state.provider_changed.emit(None)
    assert not view.action_buttons.isEnabled()


def test_metadata_collection_changed_empty_disables_buttons(qtbot, fake_provider, task_runner):
    """collection_changed with empty string disables MetadataView action buttons."""
    app_state = AppState()
    app_state.provider = fake_provider
    view = MetadataView(app_state, task_runner)
    qtbot.addWidget(view)
    view.set_collection_ready(True)
    view.app_state.collection_changed.emit("")
    assert not view.action_buttons.isEnabled()
