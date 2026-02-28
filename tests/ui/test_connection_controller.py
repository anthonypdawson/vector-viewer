"""Tests for ConnectionController and related thread classes."""

import sys
import types
from unittest.mock import MagicMock

import vector_inspector.ui.controllers.connection_controller as cc_module
from vector_inspector.ui.controllers.connection_controller import (
    ConnectionController,
    ConnectionThread,
    ModelMetadataLoadThread,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeConnection:
    def connect(self):
        return True

    def list_collections(self):
        return ["col_a", "col_b"]

    is_connected = True


class FailConnection:
    def connect(self):
        return False

    def list_collections(self):
        return []


class ExceptionConnection:
    def connect(self):
        raise RuntimeError("Cannot reach host")

    def list_collections(self):
        return []


class FakeConnectionManager:
    MAX_CONNECTIONS = 10

    def __init__(self, count=0):
        self._count = count
        self._state_updates = []
        self._opened = []
        self._collections_updates = []
        self._closed = []
        self._active_conn_id = "test_id"

    def get_connection_count(self):
        return self._count

    def get_active_connection_id(self):
        return self._active_conn_id

    def create_connection(self, name, provider, connection, config, connection_id=None):
        return connection_id or "new_id"

    def update_connection_state(self, connection_id, state, error=None):
        self._state_updates.append((connection_id, state))

    def mark_connection_opened(self, connection_id):
        self._opened.append(connection_id)

    def update_collections(self, connection_id, collections):
        self._collections_updates.append((connection_id, collections))

    def close_connection(self, connection_id):
        self._closed.append(connection_id)

    def get_connection(self, conn_id):
        return None


class FakeProfileService:
    def __init__(self, profile_data=None):
        self._profile_data = profile_data

    def get_profile_with_credentials(self, profile_id):
        return self._profile_data


class FakeLoadingDialog:
    def show_loading(self, msg=""):
        pass

    def hide_loading(self):
        pass


# ---------------------------------------------------------------------------
# ConnectionThread tests
# ---------------------------------------------------------------------------


def test_connection_thread_run_direct_success():
    thread = ConnectionThread(FakeConnection(), correlation_id="corr-1", provider="chroma")
    results = []
    thread.finished.connect(lambda s, c, e, d, corr: results.append((s, c, e)))
    thread.run()
    assert results and results[0][0] is True
    assert results[0][1] == ["col_a", "col_b"]


def test_connection_thread_run_direct_failure():
    thread = ConnectionThread(FailConnection(), correlation_id="corr-2", provider="chroma")
    results = []
    thread.finished.connect(lambda s, c, e, d, corr: results.append((s, c, e)))
    thread.run()
    assert results and results[0][0] is False
    assert "failed" in results[0][2].lower()


def test_connection_thread_run_direct_exception():
    thread = ConnectionThread(ExceptionConnection(), correlation_id="corr-3", provider="chroma")
    results = []
    thread.finished.connect(lambda s, c, e, d, corr: results.append((s, c, e)))
    thread.run()
    assert results and results[0][0] is False
    assert "Cannot reach host" in results[0][2]


# ---------------------------------------------------------------------------
# ModelMetadataLoadThread tests
# ---------------------------------------------------------------------------


def test_model_metadata_thread_run_direct_success(monkeypatch):
    class FakeProvider:
        def get_metadata(self):
            m = MagicMock()
            m.dimension = 384
            return m

    class FakeProviderFactory:
        @staticmethod
        def create(name, ptype):
            return FakeProvider()

    fake_mod = types.ModuleType("vector_inspector.core.embedding_providers")
    fake_mod.ProviderFactory = FakeProviderFactory
    monkeypatch.setitem(sys.modules, "vector_inspector.core.embedding_providers", fake_mod)

    thread = ModelMetadataLoadThread(embedder_name="all-MiniLM", embedder_type="sentence-transformer")
    dims = []
    thread.finished.connect(lambda d: dims.append(d))
    thread.run()
    assert dims == [384]


def test_model_metadata_thread_run_direct_error(monkeypatch):
    fake_provider_factory = MagicMock()
    fake_provider_factory.create.side_effect = RuntimeError("bad model")

    fake_mod = types.ModuleType("vector_inspector.core.embedding_providers")
    fake_mod.ProviderFactory = fake_provider_factory
    monkeypatch.setitem(sys.modules, "vector_inspector.core.embedding_providers", fake_mod)

    thread = ModelMetadataLoadThread(embedder_name="unknown", embedder_type="unknown")
    errors = []
    thread.error.connect(lambda e: errors.append(e))
    thread.run()
    assert errors and "bad model" in errors[0]


# ---------------------------------------------------------------------------
# ConnectionController tests
# ---------------------------------------------------------------------------


def test_connection_controller_instantiates(qtbot, monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)
    assert ctrl is not None


def test_connect_to_profile_not_found(qtbot, monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService(profile_data=None)
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())
    monkeypatch.setattr(cc_module.QMessageBox, "warning", staticmethod(lambda *a, **kw: None))

    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)
    result = ctrl.connect_to_profile("missing_id")
    assert result is False


def test_connect_to_profile_at_limit(qtbot, monkeypatch):
    mgr = FakeConnectionManager(count=10)  # At max
    svc = FakeProfileService(profile_data={"name": "DB1", "provider": "chroma", "config": {}, "id": "p1"})
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())
    monkeypatch.setattr(cc_module.QMessageBox, "warning", staticmethod(lambda *a, **kw: None))

    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)
    result = ctrl.connect_to_profile("p1")
    assert result is False


def test_on_connection_finished_success(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())

    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    completed_signals = []
    ctrl.connection_completed.connect(lambda cid, s, c, e: completed_signals.append((cid, s)))

    ctrl._on_connection_finished(
        connection_id="conn1",
        provider="chroma",
        success=True,
        collections=["col_a"],
        error="",
        duration_ms=50.0,
        correlation_id="corr-1",
    )

    assert mgr._opened == ["conn1"]
    assert any(cid == "conn1" and s is True for cid, s in completed_signals)


def test_on_connection_finished_failure(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())
    monkeypatch.setattr(cc_module.QMessageBox, "warning", staticmethod(lambda *a, **kw: None))

    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    completed_signals = []
    ctrl.connection_completed.connect(lambda cid, s, c, e: completed_signals.append((cid, s)))

    ctrl._on_connection_finished(
        connection_id="conn2",
        provider="chroma",
        success=False,
        collections=[],
        error="timeout",
        duration_ms=3000.0,
        correlation_id="corr-2",
    )

    assert "conn2" in mgr._closed
    assert any(cid == "conn2" and s is False for cid, s in completed_signals)


def test_cleanup_no_running_threads(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())

    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)
    ctrl.cleanup()  # Should not raise
