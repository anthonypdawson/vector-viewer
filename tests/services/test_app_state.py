"""Tests for AppState covering uncovered branches and properties."""

from __future__ import annotations

import pytest

from vector_inspector.state.app_state import AppState


@pytest.fixture
def app_state(qapp):
    return AppState()


# ---------------------------------------------------------------------------
# collection property
# ---------------------------------------------------------------------------


def test_collection_setter_emits_signal(app_state, qtbot):
    emitted = []
    app_state.collection_changed.connect(lambda c: emitted.append(c))

    app_state.collection = "col1"

    assert emitted == ["col1"]
    assert app_state.collection == "col1"


def test_collection_setter_no_signal_when_same(app_state, qtbot):
    app_state.collection = "col1"
    emitted = []
    app_state.collection_changed.connect(lambda c: emitted.append(c))

    app_state.collection = "col1"  # same value

    assert emitted == []


def test_collection_setter_with_none_emits_empty_string(app_state, qtbot):
    app_state.collection = "some_col"
    emitted = []
    app_state.collection_changed.connect(lambda c: emitted.append(c))

    app_state.collection = None

    assert emitted == [""]


# ---------------------------------------------------------------------------
# database property
# ---------------------------------------------------------------------------


def test_database_setter_emits_signal(app_state, qtbot):
    emitted = []
    app_state.database_changed.connect(lambda d: emitted.append(d))

    app_state.database = "my_db"

    assert emitted == ["my_db"]
    assert app_state.database == "my_db"


def test_database_setter_no_signal_when_same(app_state, qtbot):
    app_state.database = "my_db"
    emitted = []
    app_state.database_changed.connect(lambda d: emitted.append(d))

    app_state.database = "my_db"

    assert emitted == []


# ---------------------------------------------------------------------------
# set_data / set_metadata
# ---------------------------------------------------------------------------


def test_set_data_emits_vectors_loaded(app_state, qtbot):
    emitted = []
    app_state.vectors_loaded.connect(lambda d: emitted.append(d))

    data = {"ids": ["a"], "embeddings": [[1.0, 0.0]], "metadatas": [{}], "documents": ["doc"]}
    app_state.set_data(data)

    assert len(emitted) == 1
    assert app_state.vectors is not None
    assert app_state.metadata is not None
    assert app_state.full_data is data


def test_set_metadata_emits_signal(app_state, qtbot):
    emitted = []
    app_state.metadata_loaded.connect(lambda d: emitted.append(d))

    meta = {"ids": ["a"], "metadatas": [{"key": "val"}], "documents": ["doc"]}
    app_state.set_metadata(meta)

    assert len(emitted) == 1
    assert app_state.metadata is meta


# ---------------------------------------------------------------------------
# selected_ids
# ---------------------------------------------------------------------------


def test_selected_ids_setter_emits_signal(app_state, qtbot):
    emitted = []
    app_state.selection_changed.connect(lambda ids: emitted.append(ids))

    app_state.selected_ids = ["id1", "id2"]

    assert emitted == [["id1", "id2"]]


def test_selected_ids_setter_no_signal_when_same(app_state, qtbot):
    app_state.selected_ids = ["id1"]
    emitted = []
    app_state.selection_changed.connect(lambda ids: emitted.append(ids))

    app_state.selected_ids = ["id1"]  # same value

    assert emitted == []


# ---------------------------------------------------------------------------
# set_clusters / clear_clusters
# ---------------------------------------------------------------------------


def test_set_clusters_emits_signal(app_state, qtbot):
    import numpy as np

    emitted = []
    app_state.clusters_updated.connect(lambda labels, algo: emitted.append((algo,)))

    labels = np.array([0, 1, 0])
    app_state.set_clusters(labels, "KMeans")

    assert emitted == [("KMeans",)]
    assert app_state.cluster_algorithm == "KMeans"
    assert app_state.cluster_labels is labels


def test_clear_clusters_emits_signal(app_state, qtbot):
    import numpy as np

    app_state.set_clusters(np.array([0, 1]), "KMeans")

    emitted = []
    app_state.clusters_updated.connect(lambda labels, algo: emitted.append(algo))

    app_state.clear_clusters()

    assert emitted == [""]
    assert app_state.cluster_labels is None
    assert app_state.cluster_algorithm is None


def test_clear_clusters_no_signal_when_already_clear(app_state, qtbot):
    """clear_clusters does nothing if labels are already None."""
    emitted = []
    app_state.clusters_updated.connect(lambda labels, algo: emitted.append(algo))

    app_state.clear_clusters()

    assert emitted == []


# ---------------------------------------------------------------------------
# set_search_results / clear_search_results
# ---------------------------------------------------------------------------


def test_set_search_results_emits_signal(app_state, qtbot):
    emitted = []
    app_state.search_results_updated.connect(lambda r: emitted.append(r))

    results = {"ids": ["x"]}
    app_state.set_search_results(results, query="hello")

    assert emitted == [results]
    assert app_state.search_results is results
    assert app_state.search_query == "hello"


def test_set_search_results_no_query_arg(app_state, qtbot):
    """set_search_results with query=None doesn't clear previous query."""
    app_state.set_search_results({"ids": ["a"]}, query="first")
    app_state.set_search_results({"ids": ["b"]})  # no query arg

    assert app_state.search_query == "first"  # unchanged


def test_clear_search_results_emits_signal(app_state, qtbot):
    app_state.set_search_results({"ids": ["x"]}, query="q")

    emitted = []
    app_state.search_results_updated.connect(lambda r: emitted.append(r))

    app_state.clear_search_results()

    assert emitted == [{}]
    assert app_state.search_results is None
    assert app_state.search_query is None


def test_clear_search_results_no_signal_when_already_clear(app_state, qtbot):
    emitted = []
    app_state.search_results_updated.connect(lambda r: emitted.append(r))

    app_state.clear_search_results()

    assert emitted == []


# ---------------------------------------------------------------------------
# client_filters / server_filter setters
# ---------------------------------------------------------------------------


def test_client_filters_setter_emits_signal(app_state, qtbot):
    emitted = []
    app_state.filters_changed.connect(lambda f: emitted.append(f))

    app_state.client_filters = [{"field": "name", "op": "eq", "value": "Alice"}]

    assert len(emitted) == 1
    assert emitted[0]["client_filters"] == [{"field": "name", "op": "eq", "value": "Alice"}]


def test_server_filter_setter_emits_signal(app_state, qtbot):
    emitted = []
    app_state.filters_changed.connect(lambda f: emitted.append(f))

    app_state.server_filter = {"where": {"field": {"$eq": "value"}}}

    assert len(emitted) == 1
    assert emitted[0]["server_filter"] == {"where": {"field": {"$eq": "value"}}}


# ---------------------------------------------------------------------------
# active_filters setter
# ---------------------------------------------------------------------------


def test_active_filters_setter_new_format(app_state, qtbot):
    emitted = []
    app_state.filters_changed.connect(lambda f: emitted.append(f))

    app_state.active_filters = {
        "client_filters": [{"field": "x", "op": "gt", "value": 5}],
        "server_filter": {"where": {}},
    }

    assert len(emitted) == 1
    assert app_state.client_filters == [{"field": "x", "op": "gt", "value": 5}]
    assert app_state.server_filter == {"where": {}}


def test_active_filters_setter_old_format(app_state, qtbot):
    """Old format: plain dict treated as server_filter."""
    emitted = []
    app_state.filters_changed.connect(lambda f: emitted.append(f))

    app_state.active_filters = {"where": {"field": {"$eq": "val"}}}

    assert len(emitted) == 1
    assert app_state.server_filter == {"where": {"field": {"$eq": "val"}}}
    assert app_state.client_filters == []


def test_active_filters_setter_empty_dict(app_state, qtbot):
    """Setting empty dict clears filters."""
    app_state.active_filters = {"where": {"field": {"$eq": "val"}}}
    emitted = []
    app_state.filters_changed.connect(lambda f: emitted.append(f))

    app_state.active_filters = {}

    assert len(emitted) == 1


# ---------------------------------------------------------------------------
# scroll_position setter
# ---------------------------------------------------------------------------


def test_scroll_position_setter(app_state):
    app_state.scroll_position = 42
    assert app_state.scroll_position == 42


# ---------------------------------------------------------------------------
# user_inputs / set_user_input / get_user_input
# ---------------------------------------------------------------------------


def test_user_inputs_property(app_state):
    app_state.set_user_input("search_query", "hello")
    assert app_state.user_inputs["search_query"] == "hello"


def test_get_user_input_default(app_state):
    result = app_state.get_user_input("nonexistent", default="fallback")
    assert result == "fallback"


def test_get_user_input_set_value(app_state):
    app_state.set_user_input("key", 42)
    assert app_state.get_user_input("key") == 42


# ---------------------------------------------------------------------------
# set_page / page properties
# ---------------------------------------------------------------------------


def test_set_page_emits_signal(app_state, qtbot):
    emitted = []
    app_state.page_changed.connect(lambda p, ps: emitted.append((p, ps)))

    app_state.set_page(2)

    assert emitted == [(2, 100)]
    assert app_state.current_page == 2


def test_set_page_with_page_size(app_state, qtbot):
    emitted = []
    app_state.page_changed.connect(lambda p, ps: emitted.append((p, ps)))

    app_state.set_page(3, page_size=50)

    assert emitted == [(3, 50)]
    assert app_state.page_size == 50


def test_set_page_no_signal_when_unchanged(app_state, qtbot):
    app_state.set_page(1)
    emitted = []
    app_state.page_changed.connect(lambda p, ps: emitted.append((p, ps)))

    app_state.set_page(1)  # same page, no size change

    assert emitted == []


# ---------------------------------------------------------------------------
# start_loading / finish_loading / emit_error
# ---------------------------------------------------------------------------


def test_start_loading_and_finish_loading(app_state, qtbot):
    started = []
    finished = []
    app_state.loading_started.connect(lambda m: started.append(m))
    app_state.loading_finished.connect(lambda: finished.append(True))

    app_state.start_loading("Working...")
    assert started == ["Working..."]
    assert app_state.is_loading is True

    app_state.finish_loading()
    assert finished == [True]
    assert app_state.is_loading is False


def test_emit_error_sends_signal(app_state, qtbot):
    errors = []
    app_state.error_occurred.connect(lambda t, m: errors.append((t, m)))

    app_state.emit_error("Error Title", "Something went wrong")

    assert errors == [("Error Title", "Something went wrong")]


# ---------------------------------------------------------------------------
# enable_advanced_features
# ---------------------------------------------------------------------------


def test_enable_advanced_features(app_state):
    assert not app_state._advanced_features_enabled
    app_state.enable_advanced_features()
    assert app_state.advanced_features_enabled is True


def test_advanced_features_enabled_checks_vector_studio(app_state, monkeypatch):
    """When _advanced_features_enabled is False, tries to import vector_studio."""
    import sys

    app_state._advanced_features_enabled = False

    # Simulate vector_studio not installed
    monkeypatch.setitem(sys.modules, "vector_studio", None)

    result = app_state.advanced_features_enabled

    assert result is False


# ---------------------------------------------------------------------------
# get_feature_tooltip
# ---------------------------------------------------------------------------


def test_get_feature_tooltip_default(app_state):
    tooltip = app_state.get_feature_tooltip()
    assert "Vector Studio" in tooltip


def test_get_feature_tooltip_custom_name(app_state):
    tooltip = app_state.get_feature_tooltip("Advanced clustering")
    assert "Advanced clustering" in tooltip


# ---------------------------------------------------------------------------
# get_cache_key
# ---------------------------------------------------------------------------


def test_get_cache_key_with_database_and_collection(app_state):
    app_state.database = "mydb"
    app_state._collection = "mycol"

    key = app_state.get_cache_key()

    assert key == ("mydb", "mycol")


def test_get_cache_key_returns_none_when_missing(app_state):
    assert app_state.get_cache_key() is None


# ---------------------------------------------------------------------------
# provider setter clears dependent state
# ---------------------------------------------------------------------------


def test_provider_setter_clears_collection_and_database(app_state, qtbot):
    from unittest.mock import MagicMock

    app_state._collection = "some_col"
    app_state._database = "some_db"

    mock_provider = MagicMock()
    app_state.provider = mock_provider

    assert app_state._collection is None
    assert app_state._database is None
