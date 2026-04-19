import pytest


@pytest.fixture(autouse=True)
def _no_modal_install_dialog(monkeypatch):
    """Two-part guard for every test in this module:

    1. Replace ProviderInstallDialog with a non-blocking stub so tests that
       programmatically select an unavailable provider never open a modal loop.
    2. Patch get_provider_info in the connection_view module to report all
       providers as available so _on_provider_changed's fallback logic doesn't
       reset the combo back to the first available provider.

    Tests that specifically exercise the install-dialog behaviour override the
    ProviderInstallDialog patch by setting it again in their own test body
    (the later monkeypatch call wins).
    """
    import vector_inspector.ui.dialogs.provider_install_dialog as _dlg_mod
    from vector_inspector.core.provider_detection import (
        ProviderInfo,
        get_provider_info as _orig,
    )

    class _Sig:
        def connect(self, _cb):
            pass

        def emit(self, *args):
            pass

    class _InstantCloseDialog:
        provider_installed = _Sig()

        def __init__(self, provider, parent=None):
            pass

        def exec(self):
            return 0

    monkeypatch.setattr(_dlg_mod, "ProviderInstallDialog", _InstantCloseDialog)

    def _always_available(provider_id: str):
        info = _orig(provider_id)
        if info is None:
            return None
        return ProviderInfo(
            id=info.id,
            name=info.name,
            available=True,
            install_command=info.install_command,
            import_name=info.import_name,
            description=info.description,
        )

    monkeypatch.setattr(
        "vector_inspector.ui.views.connection_view.get_provider_info",
        _always_available,
    )


def make_fake_connection(success=True, raise_exc=False):
    class Fake:
        def __init__(self):
            self.connected = False

        def connect(self):
            if raise_exc:
                raise RuntimeError("connect fail")
            self.connected = success
            return success

        def list_collections(self):
            if raise_exc:
                raise RuntimeError("list fail")
            return ["c1", "c2"]

        def disconnect(self):
            self.connected = False

    return Fake()


def test_connection_thread_success(monkeypatch):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    fake = make_fake_connection(success=True)
    t = mod.ConnectionThread(fake)
    captured = {}

    def on_finished(ok, cols):
        captured["ok"] = ok
        captured["cols"] = cols

    t.finished.connect(on_finished)
    t.run()
    assert captured.get("ok") is True
    assert captured.get("cols") == ["c1", "c2"]


def test_connection_thread_exception(monkeypatch):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    fake = make_fake_connection(raise_exc=True)
    t = mod.ConnectionThread(fake)
    captured = {}

    def on_finished(ok, cols):
        captured["ok"] = ok

    t.finished.connect(on_finished)
    t.run()
    assert captured.get("ok") is False


def test_get_connection_config_and_browse(monkeypatch, tmp_path, qtbot):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)
    # Pinecone branch
    idx = dialog.provider_combo.findData("pinecone")
    dialog.provider_combo.setCurrentIndex(idx)
    dialog.api_key_input.setText("key123")
    cfg = dialog.get_connection_config()
    assert cfg["provider"] == "pinecone"
    assert cfg["api_key"] == "key123"

    # Browse for path: patch QFileDialog in the module namespace (never mutate Shiboken types directly)
    class _FakeQFileDialog:
        @staticmethod
        def getExistingDirectory(*a, **k):
            return str(tmp_path)

    monkeypatch.setattr(mod, "QFileDialog", _FakeQFileDialog)
    dialog.path_input.setText(".")
    dialog._browse_for_path()
    assert dialog.path_input.text() != ""


def test_provider_changes_enable_fields(qtbot):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)
    # pgvector enables host/port/database fields
    idx = dialog.provider_combo.findData("pgvector")
    dialog.provider_combo.setCurrentIndex(idx)
    dialog._on_provider_changed()
    assert dialog.host_input.isEnabled()
    assert dialog.database_input.isEnabled()


def test_connect_with_config_success(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    # Replace real connection classes with simple fakes
    class FakeConn:
        def __init__(self, **kwargs):
            self.host = kwargs.get("host")
            self.port = kwargs.get("port")
            self.path = kwargs.get("path")
            self.is_connected = True

        def connect(self):
            return True

        def list_collections(self):
            return ["x"]

        def disconnect(self):
            self.is_connected = False

    monkeypatch.setattr(mod, "get_connection_class", lambda _provider: FakeConn)

    # Fake thread that immediately emits finished
    class Emittable:
        def __init__(self):
            self._cb = None

        def connect(self, cb):
            self._cb = cb

        def emit(self, *a, **k):
            if self._cb:
                self._cb(*a, **k)

    class FakeThread:
        def __init__(self, connection):
            self.connection = connection
            self.finished = Emittable()

        def start(self):
            try:
                self.finished.emit(True, ["a", "b"])  # type: ignore
            except Exception:
                pass

    # Monkeypatch ConnectionThread used in _connect_with_config
    monkeypatch.setattr(mod, "ConnectionThread", FakeThread)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    # Connect with chromadb persistent
    cfg = {"provider": "chromadb", "type": "persistent", "path": "./data"}
    view._connect_with_config(cfg)
    # After fake thread, UI should reflect connected
    assert "Connected" in view.status_label.text()


def test_connect_with_config_missing_api_key(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    view = mod.ConnectionView()
    qtbot.addWidget(view)

    # QMessageBox is imported lazily inside _connect_with_config, so patch it on
    # the PySide6.QtWidgets module (a Python module object, not a Shiboken type).
    import PySide6.QtWidgets as _qtw

    class _FakeMB:
        @staticmethod
        def warning(*a, **k):
            pass

    monkeypatch.setattr(_qtw, "QMessageBox", _FakeMB)

    # Pinecone without api_key
    view._connect_with_config({"provider": "pinecone", "type": "cloud", "api_key": ""})
    # Loading dialog hidden and no connection created
    assert not getattr(view, "connection", None) or not isinstance(view.connection, mod.PineconeConnection)


def test_connection_thread_connect_returns_false():
    """connect() returns False (no exception) emits finished(False, [])."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    fake = make_fake_connection(success=False)
    t = mod.ConnectionThread(fake)
    captured = {}

    def on_finished(ok, cols):
        captured["ok"] = ok
        captured["cols"] = cols

    t.finished.connect(on_finished)
    t.run()
    assert captured.get("ok") is False
    assert captured.get("cols") == []


def test_on_provider_changed_port_updates(qtbot):
    """switching provider updates port defaults."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    # Start at chromadb with default port 8000
    dialog.port_input.setText("8000")
    idx = dialog.provider_combo.findData("qdrant")
    dialog.provider_combo.setCurrentIndex(idx)  # triggers _on_provider_changed
    # Qdrant with port "8000" → changes to "6333"
    assert dialog.port_input.text() == "6333"

    # Switch back to chromadb: port "6333" → "8000"
    idx = dialog.provider_combo.findData("chromadb")
    dialog.provider_combo.setCurrentIndex(idx)
    assert dialog.port_input.text() == "8000"


def test_on_provider_changed_pinecone_branch(qtbot):
    """switching to Pinecone disables path/host/port, enables api_key."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    idx = dialog.provider_combo.findData("pinecone")
    dialog.provider_combo.setCurrentIndex(idx)
    dialog._on_provider_changed()

    assert not dialog.path_input.isEnabled()
    assert not dialog.host_input.isEnabled()
    assert dialog.api_key_input.isEnabled()


def test_on_provider_changed_qdrant_else_branch(qtbot):
    """else branch for qdrant provider enables radio buttons."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    idx = dialog.provider_combo.findData("qdrant")
    dialog.provider_combo.setCurrentIndex(idx)

    assert dialog.persistent_radio.isEnabled()
    assert dialog.http_radio.isEnabled()
    assert dialog.ephemeral_radio.isEnabled()


def test_on_type_changed_pinecone(qtbot):
    """_on_type_changed for pinecone enables api_key, disables rest."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    dialog.provider = "pinecone"
    dialog._on_type_changed()

    assert not dialog.path_input.isEnabled()
    assert dialog.api_key_input.isEnabled()
    assert not dialog.database_input.isEnabled()


def test_on_type_changed_pgvector(qtbot):
    """_on_type_changed for pgvector enables host/port/db."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    dialog.provider = "pgvector"
    dialog._on_type_changed()

    assert dialog.host_input.isEnabled()
    assert dialog.port_input.isEnabled()
    assert dialog.database_input.isEnabled()


def test_on_type_changed_http_and_ephemeral(qtbot):
    """_on_type_changed for http and ephemeral."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    dialog.provider = "chromadb"
    dialog.http_radio.setChecked(True)
    dialog._on_type_changed()
    assert dialog.host_input.isEnabled()
    assert dialog.port_input.isEnabled()
    assert not dialog.database_input.isEnabled()

    dialog.ephemeral_radio.setChecked(True)
    dialog._on_type_changed()
    assert not dialog.path_input.isEnabled()


def test_get_connection_config_pgvector(qtbot):
    """get_connection_config PgVector branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    idx = dialog.provider_combo.findData("pgvector")
    dialog.provider_combo.setCurrentIndex(idx)
    dialog.port_input.setText("5432")
    cfg = dialog.get_connection_config()
    assert cfg["provider"] == "pgvector"
    assert cfg["type"] == "pgvector"
    assert cfg["port"] == 5432


def test_get_connection_config_http_and_ephemeral(qtbot):
    """get_connection_config http and ephemeral branches."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    # HTTP branch
    dialog.provider_combo.setCurrentIndex(dialog.provider_combo.findData("chromadb"))
    dialog.http_radio.setChecked(True)
    dialog.host_input.setText("my-host")
    dialog.port_input.setText("9000")
    cfg = dialog.get_connection_config()
    assert cfg["type"] == "http"
    assert cfg["host"] == "my-host"
    assert cfg["port"] == 9000

    # Ephemeral branch
    dialog.ephemeral_radio.setChecked(True)
    cfg = dialog.get_connection_config()
    assert cfg["type"] == "ephemeral"


def test_load_last_connection_cloud(monkeypatch, qtbot):
    """_load_last_connection cloud (Pinecone) branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    class FakeSettings:
        def get_last_connection(self):
            return {"provider": "pinecone", "type": "cloud", "api_key": "my-key", "auto_connect": False}

        def save_last_connection(self, c):
            pass

    monkeypatch.setattr(mod, "SettingsService", FakeSettings)
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    assert dialog.api_key_input.text() == "my-key"


def test_load_last_connection_pgvector(monkeypatch, qtbot):
    """_load_last_connection pgvector branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    class FakeSettings:
        def get_last_connection(self):
            return {
                "provider": "pgvector",
                "type": "pgvector",
                "host": "pg-host",
                "port": 5432,
                "database": "mydb",
                "user": "user1",
                "password": "pw",
                "auto_connect": False,
            }

        def save_last_connection(self, c):
            pass

    monkeypatch.setattr(mod, "SettingsService", FakeSettings)
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    assert dialog.host_input.text() == "pg-host"
    assert dialog.database_input.text() == "mydb"


def test_load_last_connection_http(monkeypatch, qtbot):
    """_load_last_connection http branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    class FakeSettings:
        def get_last_connection(self):
            return {
                "provider": "chromadb",
                "type": "http",
                "host": "remote-host",
                "port": 8000,
                "api_key": "apikey123",
                "auto_connect": False,
            }

        def save_last_connection(self, c):
            pass

    monkeypatch.setattr(mod, "SettingsService", FakeSettings)
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    assert dialog.host_input.text() == "remote-host"
    assert dialog.api_key_input.text() == "apikey123"


def test_load_last_connection_ephemeral(monkeypatch, qtbot):
    """_load_last_connection ephemeral branch + auto_connect."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    class FakeSettings:
        def get_last_connection(self):
            return {"provider": "chromadb", "type": "ephemeral", "auto_connect": True}

        def save_last_connection(self, c):
            pass

    monkeypatch.setattr(mod, "SettingsService", FakeSettings)
    dialog = mod.ConnectionDialog()
    qtbot.addWidget(dialog)

    assert dialog.ephemeral_radio.isChecked()
    assert dialog.auto_connect_check.isChecked()


def _make_fake_connection_view_dependencies(monkeypatch, mod):
    """Helper: patch all connection classes and ConnectionThread with synchronous fakes."""

    class FakeConn:
        def __init__(self, **kwargs):
            self.host = kwargs.get("host")
            self.port = kwargs.get("port")
            self.path = kwargs.get("path")

        def connect(self):
            return True

        def list_collections(self):
            return ["col1"]

        def disconnect(self):
            pass

    class SyncThread:
        class _Signal:
            def __init__(self):
                self._cbs = []

            def connect(self, cb):
                self._cbs.append(cb)

            def emit(self, *args):
                for cb in self._cbs:
                    cb(*args)

        finished = None  # set per instance

        def __init__(self, connection):
            self.connection = connection
            self.finished = SyncThread._Signal()

        def start(self):
            ok = self.connection.connect()
            cols = self.connection.list_collections() if ok else []
            self.finished.emit(ok, cols)

    # connection_view uses get_connection_class() lazily, not module-level names.
    # Patch get_connection_class in the module so every provider returns FakeConn.
    monkeypatch.setattr(mod, "get_connection_class", lambda _provider: FakeConn)
    monkeypatch.setattr(mod, "ConnectionThread", SyncThread)
    return FakeConn, SyncThread


def test_connect_with_config_qdrant_persistent(monkeypatch, qtbot):
    """_connect_with_config qdrant persistent branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    view._connect_with_config({"provider": "qdrant", "type": "persistent", "path": "./data"})
    assert "Connected" in view.status_label.text()


def test_connect_with_config_qdrant_http(monkeypatch, qtbot):
    """_connect_with_config qdrant http branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    view._connect_with_config({"provider": "qdrant", "type": "http", "host": "host", "port": 6333, "api_key": "k"})
    assert "Connected" in view.status_label.text()


def test_connect_with_config_qdrant_ephemeral(monkeypatch, qtbot):
    """_connect_with_config qdrant ephemeral branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    view._connect_with_config({"provider": "qdrant", "type": "ephemeral"})
    assert "Connected" in view.status_label.text()


def test_connect_with_config_pgvector(monkeypatch, qtbot):
    """_connect_with_config pgvector branch."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    view._connect_with_config(
        {
            "provider": "pgvector",
            "host": "localhost",
            "port": 5432,
            "database": "db",
            "user": "u",
            "password": "p",
        }
    )
    assert "Connected" in view.status_label.text()


def test_on_connection_finished_failure(monkeypatch, qtbot):
    """_on_connection_finished failure path."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    emitted = []
    view.connection_changed.connect(lambda ok: emitted.append(ok))
    view._on_connection_finished(False, [])

    assert "failed" in view.status_label.text().lower()
    assert view.connect_button.isEnabled()
    assert not view.disconnect_button.isEnabled()
    assert emitted == [False]


def test_disconnect(monkeypatch, qtbot):
    """_disconnect updates UI and emits signal."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    # First connect
    view._connect_with_config({"provider": "chromadb", "type": "persistent", "path": "./data"})

    emitted = []
    view.connection_changed.connect(lambda ok: emitted.append(ok))
    view._disconnect()

    assert "Not connected" in view.status_label.text()
    assert view.connect_button.isEnabled()
    assert not view.disconnect_button.isEnabled()
    assert False in emitted


def test_try_auto_connect(monkeypatch, qtbot):
    """_try_auto_connect connects when auto_connect is True."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    class FakeSettings:
        def get_last_connection(self):
            return {"provider": "chromadb", "type": "persistent", "path": "./data", "auto_connect": True}

        def save_last_connection(self, c):
            pass

    monkeypatch.setattr(mod, "SettingsService", FakeSettings)

    view = mod.ConnectionView()
    qtbot.addWidget(view)

    assert "Connected" in view.status_label.text()


def test_show_connection_dialog_accepted(monkeypatch, qtbot):
    """show_connection_dialog when dialog is accepted."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])
    _make_fake_connection_view_dependencies(monkeypatch, mod)

    captured_config = {}

    class FakeDialog:
        def __init__(self, parent=None):
            pass

        def exec(self):
            from PySide6.QtWidgets import QDialog

            return QDialog.DialogCode.Accepted

        def get_connection_config(self):
            return {"provider": "chromadb", "type": "persistent", "path": "./data", "auto_connect": False}

    monkeypatch.setattr(mod, "ConnectionDialog", FakeDialog)

    view = mod.ConnectionView()
    qtbot.addWidget(view)
    view.show_connection_dialog()

    assert "Connected" in view.status_label.text()


# ---------------------------------------------------------------------------
# _on_provider_changed — install dialog path
# ---------------------------------------------------------------------------


def test_on_provider_changed_unavailable_opens_install_dialog(monkeypatch, qtbot):
    """Selecting an unavailable provider opens ProviderInstallDialog, not a plain QMessageBox."""
    from vector_inspector.core.provider_detection import ProviderInfo

    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    # Mark qdrant as unavailable; chromadb as available so there's a fallback.
    def fake_get_all_providers():
        return [
            ProviderInfo("chromadb", "ChromaDB", True, "pip install vector-inspector[chromadb]", "chromadb", ""),
            ProviderInfo("qdrant", "Qdrant", False, "pip install vector-inspector[qdrant]", "qdrant_client", ""),
        ]

    def fake_get_provider_info(pid):
        for p in fake_get_all_providers():
            if p.id == pid:
                return p
        return None

    monkeypatch.setattr(mod, "get_all_providers", fake_get_all_providers)
    monkeypatch.setattr(mod, "get_provider_info", fake_get_provider_info)

    dialog_execs: list[str] = []

    class FakeInstallDialog:
        class _Sig:
            def connect(self, _cb):
                pass

        provider_installed = _Sig()

        def __init__(self, provider, parent=None):
            dialog_execs.append(provider.id)

        def exec(self):
            pass  # user cancels (no install)

    # _on_provider_changed uses a local import, so patch the source module.
    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog.ProviderInstallDialog",
        FakeInstallDialog,
    )

    conn_dialog = mod.ConnectionDialog()
    qtbot.addWidget(conn_dialog)

    # Block signals so setCurrentIndex doesn't fire _on_provider_changed a second
    # time before we call it explicitly below.
    conn_dialog.provider_combo.blockSignals(True)
    conn_dialog.provider_combo.addItem("Qdrant (not installed)", "qdrant")
    idx = conn_dialog.provider_combo.findData("qdrant")
    conn_dialog.provider_combo.setCurrentIndex(idx)
    conn_dialog.provider_combo.blockSignals(False)

    conn_dialog._on_provider_changed()

    assert "qdrant" in dialog_execs


def test_on_provider_changed_unavailable_falls_back_after_cancel(monkeypatch, qtbot):
    """After the install dialog closes without success the combo reverts to chromadb."""
    from vector_inspector.core.provider_detection import ProviderInfo

    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    def fake_get_all_providers():
        return [
            ProviderInfo("chromadb", "ChromaDB", True, "pip install vector-inspector[chromadb]", "chromadb", ""),
            ProviderInfo("qdrant", "Qdrant", False, "pip install vector-inspector[qdrant]", "qdrant_client", ""),
        ]

    def fake_get_provider_info(pid):
        for p in fake_get_all_providers():
            if p.id == pid:
                return p
        return None

    monkeypatch.setattr(mod, "get_all_providers", fake_get_all_providers)
    monkeypatch.setattr(mod, "get_provider_info", fake_get_provider_info)

    class FakeInstallDialog:
        class _Sig:
            def connect(self, _cb):
                pass

        provider_installed = _Sig()

        def __init__(self, provider, parent=None):
            pass

        def exec(self):
            pass  # cancelled — qdrant remains unavailable

    # Patch at the source module (local import inside _on_provider_changed).
    monkeypatch.setattr(
        "vector_inspector.ui.dialogs.provider_install_dialog.ProviderInstallDialog",
        FakeInstallDialog,
    )

    conn_dialog = mod.ConnectionDialog()
    qtbot.addWidget(conn_dialog)

    conn_dialog.provider_combo.blockSignals(True)
    conn_dialog.provider_combo.addItem("Qdrant (not installed)", "qdrant")
    idx = conn_dialog.provider_combo.findData("qdrant")
    conn_dialog.provider_combo.setCurrentIndex(idx)
    conn_dialog.provider_combo.blockSignals(False)

    conn_dialog._on_provider_changed()

    # After cancel the combo should have fallen back to the first available provider
    assert conn_dialog.provider_combo.currentData() == "chromadb"


def test_refresh_providers_silent_suppresses_messagebox(qtbot):
    """_refresh_providers(silent=True) completes without showing any modal dialog."""
    mod = __import__("vector_inspector.ui.views.connection_view", fromlist=["*"])

    conn_dialog = mod.ConnectionDialog()
    qtbot.addWidget(conn_dialog)
    # Must not block, must not raise — the silent path skips QMessageBox entirely.
    conn_dialog._refresh_providers(silent=True)
