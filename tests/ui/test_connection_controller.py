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
    assert "failed" in str(results[0][2]).lower()


def test_connection_thread_run_direct_exception():
    thread = ConnectionThread(ExceptionConnection(), correlation_id="corr-3", provider="chroma")
    results = []
    thread.finished.connect(lambda s, c, e, d, corr: results.append((s, c, e)))
    thread.run()
    assert results and results[0][0] is False
    assert "Cannot reach host" in str(results[0][2])


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


def test_save_embedding_model_config(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    called = {}

    class FakeSettings:
        def save_embedding_model(self, **kw):
            called.update(kw)

    # Patch the real SettingsService used inside the controller helper.
    # Note: the controller imports SettingsService inside the helper method,
    # so we patch the original service path. This is intentional — if the
    # implementation moves the import location the test will need updating.
    monkeypatch.setattr(
        "vector_inspector.services.settings_service.SettingsService",
        FakeSettings,
        raising=True,
    )

    conn = type("C", (), {"name": "profileA"})()
    ctrl._save_embedding_model_config(conn, "conn1", "col1", {"embedder_name": "m", "embedder_type": "t"})

    assert called.get("profile_name") == "profileA"
    assert called.get("collection_name") == "col1"
    assert called.get("model_name") == "m"


def test_refresh_collections_after_creation(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    class Conn:
        def list_collections(self):
            return ["a", "b"]

    conn = Conn()
    ctrl._refresh_collections_after_creation(conn, "conn1")
    assert mgr._collections_updates and mgr._collections_updates[-1] == ("conn1", ["a", "b"])


def test_handle_collection_complete_calls_helpers(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    # patch helpers to observe calls
    called = {"save": False, "refresh": False}
    monkeypatch.setattr(ctrl, "_save_embedding_model_config", lambda *a, **k: called.__setitem__("save", True))
    monkeypatch.setattr(
        ctrl, "_refresh_collections_after_creation", lambda *a, **k: called.__setitem__("refresh", True)
    )

    # patch QMessageBox to avoid GUI
    monkeypatch.setattr(cc_module.QMessageBox, "information", staticmethod(lambda *a, **k: None))
    monkeypatch.setattr(cc_module.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    class Progress:
        def setValue(self, *a, **k):
            pass

        def close(self, *a, **k):
            pass

    progress = Progress()
    conn = type("C", (), {"name": "p"})()
    ctrl._handle_collection_complete(
        connection=conn,
        connection_id="c",
        collection_name="col",
        config={"add_sample": True, "embedder_name": "m", "embedder_type": "t"},
        progress_dialog=progress,
        success=True,
        message="ok",
    )

    assert called["save"] is True
    assert called["refresh"] is True


def test_handle_collection_complete_failure_and_no_save_or_refresh(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    # patch helpers to observe calls
    called = {"save": False, "refresh": False}
    monkeypatch.setattr(ctrl, "_save_embedding_model_config", lambda *a, **k: called.__setitem__("save", True))
    monkeypatch.setattr(
        ctrl, "_refresh_collections_after_creation", lambda *a, **k: called.__setitem__("refresh", True)
    )

    # patch QMessageBox to capture warning invocation
    warned = {"called": False}
    monkeypatch.setattr(
        cc_module.QMessageBox, "warning", staticmethod(lambda *a, **k: warned.__setitem__("called", True))
    )
    monkeypatch.setattr(cc_module.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    class Progress:
        def setValue(self, *a, **k):
            pass

        def close(self, *a, **k):
            pass

    progress = Progress()
    conn = type("C", (), {"name": "p"})()
    # success=False should trigger warning and NOT call save or refresh
    ctrl._handle_collection_complete(
        connection=conn,
        connection_id="c",
        collection_name="col",
        config={"add_sample": True, "embedder_name": "m", "embedder_type": "t"},
        progress_dialog=progress,
        success=False,
        message="failed",
    )

    assert warned["called"] is True
    assert called["save"] is False
    assert called["refresh"] is False


def test_handle_collection_complete_no_sample_does_not_save_but_refreshes(monkeypatch):
    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    # patch helpers to observe calls
    called = {"save": False, "refresh": False}
    monkeypatch.setattr(ctrl, "_save_embedding_model_config", lambda *a, **k: called.__setitem__("save", True))
    monkeypatch.setattr(
        ctrl, "_refresh_collections_after_creation", lambda *a, **k: called.__setitem__("refresh", True)
    )

    # patch QMessageBox to avoid GUI
    monkeypatch.setattr(cc_module.QMessageBox, "information", staticmethod(lambda *a, **k: None))

    class Progress:
        def setValue(self, *a, **k):
            pass

        def close(self, *a, **k):
            pass

    progress = Progress()
    conn = type("C", (), {"name": "p"})()
    # add_sample=False should NOT call save, but should refresh
    ctrl._handle_collection_complete(
        connection=conn,
        connection_id="c",
        collection_name="col",
        config={"add_sample": False, "embedder_name": "m", "embedder_type": "t"},
        progress_dialog=progress,
        success=True,
        message="ok",
    )

    assert called["save"] is False
    assert called["refresh"] is True


# ---------------------------------------------------------------------------
# duration_ms in connection_completed signal
# ---------------------------------------------------------------------------


def test_connection_completed_signal_includes_duration_ms(monkeypatch):
    """connection_completed signal emits a float duration_ms as its 5th element."""
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())

    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    received: list = []
    ctrl.connection_completed.connect(lambda *args: received.append(args))

    ctrl._on_connection_finished(
        connection_id="test_id",
        provider="chroma",
        success=True,
        collections=["a", "b"],
        error=None,
        duration_ms=350.0,
        correlation_id="corr1",
    )

    assert len(received) == 1
    args = received[0]
    # Signal: (connection_id, success, collections, error_msg, duration_ms)
    assert args[0] == "test_id"  # connection_id
    assert args[1] is True  # success
    assert isinstance(args[4], float)  # duration_ms is float
    assert args[4] == 350.0


def test_on_connection_finished_failure_emits_duration_ms(monkeypatch):
    """duration_ms is emitted even on connection failure."""
    monkeypatch.setattr(cc_module, "LoadingDialog", lambda msg, parent: FakeLoadingDialog())
    monkeypatch.setattr(cc_module.QMessageBox, "warning", staticmethod(lambda *a, **k: None))

    mgr = FakeConnectionManager()
    svc = FakeProfileService()
    ctrl = ConnectionController(connection_manager=mgr, profile_service=svc)

    received: list = []
    ctrl.connection_completed.connect(lambda *args: received.append(args))

    ctrl._on_connection_finished(
        connection_id="fail_id",
        provider="chroma",
        success=False,
        collections=[],
        error=Exception("timeout"),
        duration_ms=120.0,
        correlation_id="corr2",
    )

    assert len(received) == 1
    args = received[0]
    assert args[1] is False
    assert isinstance(args[4], float)
    assert args[4] == 120.0
