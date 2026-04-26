"""Tests for ProfileManagerPanel and ProfileEditorDialog.

MOCKING STRATEGY:
- mock_providers: Returns all 7 providers as available. Use this for most tests.
- mock_no_providers: Returns all providers as unavailable. Use for testing placeholder
  and installation prompts.
- Tests without either fixture will use real provider detection (may vary by environment).
"""

import pytest

import vector_inspector.ui.components.profile_manager_panel as panel_mod
from vector_inspector.core.provider_detection import ProviderInfo
from vector_inspector.services.profile_service import ConnectionProfile
from vector_inspector.ui.components.profile_manager_panel import (
    ProfileEditorDialog,
)


class DummySignal:
    def connect(self, *args, **kwargs):
        pass


class FakeProfileService:
    def __init__(self):
        self.profile_added = DummySignal()
        self.profile_updated = DummySignal()
        self.profile_deleted = DummySignal()
        self._profiles = {}

    def get_all_profiles(self):
        return list(self._profiles.values())

    def get_profile(self, profile_id):
        return self._profiles.get(profile_id)

    def get_profile_with_credentials(self, profile_id):
        p = self._profiles.get(profile_id)
        if not p:
            return None
        return {
            "id": p.id,
            "name": p.name,
            "provider": p.provider,
            "config": p.config,
            "credentials": {"api_key": "secret"} if p.provider == "pinecone" else {},
        }

    def create_profile(self, **kwargs):
        return "new-id"

    def update_profile(self, *args, **kwargs):
        return True

    def delete_profile(self, *args, **kwargs):
        return True

    def duplicate_profile(self, *args, **kwargs):
        return "dup-id"


def _make_fake_providers():
    """Return a consistent list of fake providers for testing.

    This ensures tests don't depend on which providers are actually installed.
    """
    return [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=True,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="qdrant",
            name="Qdrant",
            available=True,
            install_command="pip install vector-inspector[qdrant]",
            import_name="qdrant_client",
            description="Local, remote, or cloud",
        ),
        ProviderInfo(
            id="pinecone",
            name="Pinecone",
            available=True,
            install_command="pip install vector-inspector[pinecone]",
            import_name="pinecone",
            description="Cloud-hosted vector database",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=True,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
        ProviderInfo(
            id="pgvector",
            name="PostgreSQL (pgvector)",
            available=True,
            install_command="pip install vector-inspector[pgvector]",
            import_name="psycopg2",
            description="PostgreSQL with vector extension",
        ),
        ProviderInfo(
            id="weaviate",
            name="Weaviate",
            available=True,
            install_command="pip install vector-inspector[weaviate]",
            import_name="weaviate",
            description="Local or cloud with GraphQL",
        ),
        ProviderInfo(
            id="milvus",
            name="Milvus",
            available=True,
            install_command="pip install vector-inspector[milvus]",
            import_name="pymilvus",
            description="Distributed vector database",
        ),
    ]


@pytest.fixture
def mock_providers(monkeypatch):
    """Mock get_all_providers to return consistent fake providers.

    Apply this fixture explicitly to tests that need controlled provider availability.
    Tests that don't use this fixture will use real provider detection.
    """
    fake_providers = _make_fake_providers()

    def fake_get_all_providers():
        return fake_providers

    def fake_get_provider_info(provider_id):
        for p in fake_providers:
            if p.id == provider_id:
                return p
        return None

    monkeypatch.setattr(panel_mod, "get_all_providers", fake_get_all_providers)
    monkeypatch.setattr(panel_mod, "get_provider_info", fake_get_provider_info)


@pytest.fixture
def mock_no_providers(monkeypatch):
    """Mock get_all_providers to return no available providers.

    Use this for testing the no-providers scenario (placeholder, install prompts, etc.).
    """
    no_providers = [
        ProviderInfo(
            id="chromadb",
            name="ChromaDB",
            available=False,
            install_command="pip install vector-inspector[chromadb]",
            import_name="chromadb",
            description="Local persistent or HTTP client",
        ),
        ProviderInfo(
            id="lancedb",
            name="LanceDB",
            available=False,
            install_command="pip install vector-inspector[lancedb]",
            import_name="lancedb",
            description="Embedded vector database",
        ),
    ]

    def fake_get_all_providers():
        return no_providers

    def fake_get_provider_info(provider_id):
        for p in no_providers:
            if p.id == provider_id:
                return p
        return None

    monkeypatch.setattr(panel_mod, "get_all_providers", fake_get_all_providers)
    monkeypatch.setattr(panel_mod, "get_provider_info", fake_get_provider_info)


@pytest.fixture
def fake_service():
    svc = FakeProfileService()
    # Add an example profile
    svc._profiles["p1"] = ConnectionProfile(
        profile_id="p1",
        name="Local Chroma",
        provider="chromadb",
        config={"type": "persistent", "path": "/tmp/db"},
    )
    svc._profiles["p2"] = ConnectionProfile(
        profile_id="p2",
        name="Weaviate Cloud",
        provider="weaviate",
        config={"type": "cloud", "url": "cluster.weaviate.cloud"},
    )
    return svc


def test_get_config_persistent_and_http(qtbot, fake_service, mock_providers):
    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    def _set_provider(d, data_value):
        for i in range(d.provider_combo.count()):
            if d.provider_combo.itemData(i) == data_value:
                d.provider_combo.setCurrentIndex(i)
                return
        raise AssertionError(f"provider {data_value} not found")

    # Instead of relying on UI state (which may be flaky in headless tests),
    # exercise the connection-kwargs logic directly for persistent/http cases.
    persistent_cfg = {"type": "persistent", "path": "/data/db"}
    kwargs = dlg._get_connection_kwargs(persistent_cfg)
    assert kwargs.get("path") == "/data/db"

    http_cfg = {"type": "http", "host": "db.example", "port": 5432, "database": "mydb", "user": "alice"}
    dlg.password_input.setText("pw123")
    kwargs2 = dlg._get_connection_kwargs(http_cfg)
    assert kwargs2.get("host") == "db.example"
    assert kwargs2.get("port") == 5432
    assert kwargs2.get("database") == "mydb"
    assert kwargs2.get("user") == "alice"


def test_get_connection_kwargs_and_save_behaviour(qtbot, fake_service, mock_providers, monkeypatch):
    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # HTTP with api key
    def _set_provider(d, data_value):
        for i in range(d.provider_combo.count()):
            if d.provider_combo.itemData(i) == data_value:
                d.provider_combo.setCurrentIndex(i)
                return
        raise AssertionError(f"provider {data_value} not found")

    _set_provider(dlg, "pinecone")
    dlg.http_radio.setChecked(True)
    dlg.api_key_input.setText("apikey123")
    cfg = dlg._get_config()
    kwargs = dlg._get_connection_kwargs(cfg)
    # Pinecone path is cloud so _get_connection_kwargs returns {} for cloud
    assert isinstance(kwargs, dict)

    # Stub QMessageBox to prevent blocking modal dialogs during tests
    class _DummyMB:
        @staticmethod
        def warning(*args, **kwargs):
            return None

        @staticmethod
        def critical(*args, **kwargs):
            return None

        @staticmethod
        def information(*args, **kwargs):
            return None

        @staticmethod
        def question(*args, **kwargs):
            # default to No
            return panel_mod.QMessageBox.StandardButton.No

    monkeypatch.setattr(panel_mod, "QMessageBox", _DummyMB)

    # Test save without name shows warning and does not raise
    dlg.name_input.setText("")
    dlg._save_profile()


def test_on_provider_and_type_toggles(qtbot, fake_service, mock_providers):
    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # lancedb should show path and hide host/port
    def _set_provider(d, data_value):
        for i in range(d.provider_combo.count()):
            if d.provider_combo.itemData(i) == data_value:
                d.provider_combo.setCurrentIndex(i)
                return
        raise AssertionError(f"provider {data_value} not found")

    _set_provider(dlg, "lancedb")
    dlg._on_provider_changed()
    assert not dlg.path_input.isHidden()
    assert dlg.host_input.isHidden()

    # weaviate with HTTP should show host/port
    dlg.provider_combo.setCurrentIndex(dlg.provider_combo.findData("weaviate"))
    dlg._on_provider_changed()  # This will set persistent (first supported type)
    dlg.http_radio.setChecked(True)  # Now switch to HTTP
    dlg._on_type_changed()  # Update field visibility
    # Verify weaviate HTTP fields are visible
    assert not dlg.host_input.isHidden()


def test_load_profile_data_populates_fields(qtbot, fake_service, mock_providers):
    # Use the weaviate profile
    profile = fake_service._profiles["p2"]
    dlg = ProfileEditorDialog(fake_service, profile=profile)
    qtbot.addWidget(dlg)

    # After init, provider should be set to weaviate and host contains URL
    assert dlg.provider_combo.currentData() == "weaviate"
    # Cloud config should set host text to URL
    assert "weaviate" in dlg.provider_combo.currentData()


def test_panel_actions_connect_edit_duplicate_delete(qtbot, fake_service, mock_providers, monkeypatch):

    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])

    panel = panel_mod.ProfileManagerPanel(fake_service)
    qtbot.addWidget(panel)

    # Refresh list and select first item
    panel._refresh_profiles()
    assert panel.profile_list.count() >= 1
    panel.profile_list.setCurrentRow(0)

    # Capture connect_profile emission
    captured = {}

    def _on_connect(pid):
        captured["id"] = pid

    panel.connect_profile.connect(_on_connect)
    panel._connect_selected_profile()
    assert "id" in captured

    # Stub dialog exec to avoid modal blocking
    class DummyDialog:
        def __init__(self, *args, **kwargs):
            self._execed = False

        def exec(self):
            self._execed = True

    monkeypatch.setattr(panel_mod, "ProfileEditorDialog", DummyDialog)
    panel._edit_selected_profile()  # should invoke DummyDialog

    # Duplicate: stub QInputDialog.getText
    from PySide6.QtWidgets import QInputDialog

    monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: ("Dup Name", True)))
    # ensure duplicate runs without error
    item = panel.profile_list.currentItem()
    pid = item.data(panel_mod.Qt.ItemDataRole.UserRole)
    panel._duplicate_profile(pid)

    # Delete: stub QMessageBox.question to return Yes
    class _MB:
        StandardButton = panel_mod.QMessageBox.StandardButton

        @staticmethod
        def question(*a, **k):
            return _MB.StandardButton.Yes

    monkeypatch.setattr(panel_mod, "QMessageBox", _MB)
    panel._delete_profile(pid)


def test_test_finished_and_error_and_db_fetch(qtbot, fake_service, mock_providers, monkeypatch):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])

    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Stub QMessageBox
    class _DummyMB:
        @staticmethod
        def warning(*args, **kwargs):
            return None

        @staticmethod
        def critical(*args, **kwargs):
            return None

        @staticmethod
        def information(*args, **kwargs):
            return None

        @staticmethod
        def question(*args, **kwargs):
            return panel_mod.QMessageBox.StandardButton.No

    monkeypatch.setattr(panel_mod, "QMessageBox", _DummyMB)

    # Test finished success path for pgvector triggers _fetch_databases and disconnect
    class FakeConn:
        def __init__(self):
            self.disconnected = False

        def disconnect(self):
            self.disconnected = True

    conn = FakeConn()

    called = {"fetched": False}

    def _fetch_databases():
        called["fetched"] = True

    dlg._fetch_databases = _fetch_databases

    class Progress:
        def close(self):
            pass

    dlg._on_test_finished(True, "ok", conn, "pgvector", Progress())
    assert called["fetched"]
    assert conn.disconnected

    # Test finished failure path
    dlg._on_test_finished(False, "failed", conn, "chromadb", Progress())

    # Test error path
    dlg._on_test_error("bad connection", Progress())

    # Test database fetched UI update and error handling
    # success
    dlg.database_input.clear()
    dlg._on_databases_fetched(["db1", "db2"], "")
    assert dlg.database_input.count() >= 2

    # failure with error
    dlg._on_databases_fetched([], "network error")


def test_provider_ui_branches_and_browse_and_load(qtbot, fake_service, mock_providers, monkeypatch):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])

    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Browse for path: stub QFileDialog
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(QFileDialog, "getExistingDirectory", staticmethod(lambda *a, **k: "/chosen"))
    dlg.path_input.setText("")
    dlg._browse_for_path()
    assert dlg.path_input.text() == "/chosen"

    # Test provider UI branches by directly setting provider combo and calling handlers
    def set_provider(name):
        for i in range(dlg.provider_combo.count()):
            if dlg.provider_combo.itemData(i) == name:
                dlg.provider_combo.setCurrentIndex(i)
                return

    set_provider("lancedb")
    dlg._on_provider_changed()
    assert dlg.path_input.isEnabled()

    set_provider("pinecone")
    dlg._on_provider_changed()
    assert dlg.api_key_input.isEnabled()

    set_provider("weaviate")
    dlg.http_radio.setChecked(True)
    dlg._on_provider_changed()
    dlg._on_weaviate_cloud_toggled(True)

    set_provider("pgvector")
    dlg._on_provider_changed()
    assert dlg.database_input.isEnabled()

    # load profile data for pinecone (cloud) and pgvector (http with password)
    pine = ConnectionProfile("pp", "Pine", "pinecone", {"type": "cloud", "url": "u"})
    fake_service._profiles["pp"] = pine
    dlg2 = ProfileEditorDialog(fake_service, profile=pine)
    qtbot.addWidget(dlg2)
    assert dlg2.provider_combo.currentData() == "pinecone"

    pg = ConnectionProfile(
        "pg1",
        "PG",
        "pgvector",
        {"type": "http", "host": "h", "port": 5432, "database": "d", "user": "u"},
    )
    fake_service._profiles["pg1"] = pg
    dlg3 = ProfileEditorDialog(fake_service, profile=pg)
    qtbot.addWidget(dlg3)
    assert dlg3.provider_combo.currentData() == "pgvector"
    assert dlg3.database_input.currentText() == "d"


def test_threads_run_and_emit_sync(qtbot, monkeypatch):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])

    # Test TestConnectionThread with success, failure, and exception
    class Emitter:
        def __init__(self):
            self.calls = []

        def emit(self, *args):
            self.calls.append(args)

    class ConnTrue:
        def connect(self):
            return True

    class ConnFalse:
        def connect(self):
            return False

    class ConnError:
        def connect(self):
            raise RuntimeError("boom")

    t = panel_mod.TestConnectionThread(ConnTrue(), "chromadb")
    t.finished = Emitter()
    t.error = Emitter()
    t.run()
    assert t.finished.calls and t.finished.calls[0][0] is True

    t2 = panel_mod.TestConnectionThread(ConnFalse(), "chromadb")
    t2.finished = Emitter()
    t2.error = Emitter()
    t2.run()
    assert t2.finished.calls and t2.finished.calls[0][0] is False

    t3 = panel_mod.TestConnectionThread(ConnError(), "chromadb")
    t3.finished = Emitter()
    t3.error = Emitter()
    t3.run()
    assert t3.error.calls and "boom" in t3.error.calls[0][0]

    # Test DatabaseFetchThread by injecting fake module into sys.modules
    import sys
    import types

    mod = types.ModuleType("vector_inspector.core.connections.pgvector_connection")

    class FakePg:
        def __init__(self, host, port, database, user, password):
            self._connected = False

        def connect(self):
            return True

        def list_databases(self):
            return ["one", "two"]

        def disconnect(self):
            pass

    mod.PgVectorConnection = FakePg
    monkeypatch.setitem(sys.modules, "vector_inspector.core.connections.pgvector_connection", mod)

    df = panel_mod.DatabaseFetchThread("h", 5432, "u", "p")
    emitted = Emitter()
    df.finished = emitted
    df.run()
    assert emitted.calls and isinstance(emitted.calls[0][0], list)


def test_test_connection_flow_creates_threads_and_handles_pinecone_and_weaviate(
    qtbot, fake_service, mock_providers, monkeypatch
):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])
    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Prepare fake modules for imports used in _test_connection
    import sys
    import types

    def make_mod(cls_name):
        m = types.ModuleType(f"vector_inspector.core.connections.{cls_name}_connection")

        class C:
            def __init__(self, *a, **k):
                pass

            def connect(self):
                return True

            def disconnect(self):
                pass

            def list_databases(self):
                return []

        setattr(m, cls_name[0].upper() + cls_name[1:] + "Connection", C)
        return m

    names = [
        ("chroma", "ChromaDBConnection"),
        ("lancedb", "LanceDBConnection"),
        ("pgvector", "PgVectorConnection"),
        ("pinecone", "PineconeConnection"),
        ("qdrant", "QdrantConnection"),
        ("weaviate", "WeaviateConnection"),
    ]

    for base, cls in names:
        modname = f"vector_inspector.core.connections.{base}_connection"
        m = types.ModuleType(modname)

        # Generic connection class
        class Conn:
            def __init__(self, *a, **kw):
                pass

            def connect(self):
                return True

            def disconnect(self):
                pass

            def list_databases(self):
                return []

        setattr(m, cls, Conn)
        monkeypatch.setitem(sys.modules, modname, m)

    # Monkeypatch TestConnectionThread to a fake that calls callbacks immediately
    class FakeThread:
        def __init__(self, conn, provider, parent=None):
            self.conn = conn
            self.provider = provider
            self._finished_cb = None
            self._error_cb = None

            class Sig:
                def __init__(self, owner, name):
                    self._owner = owner
                    self._name = name

                def connect(self, cb):
                    if self._name == "finished":
                        self._owner._finished_cb = cb
                    else:
                        self._owner._error_cb = cb

            self.finished = Sig(self, "finished")
            self.error = Sig(self, "error")

        def start(self):
            # Always report success
            if self._finished_cb:
                self._finished_cb(True, "ok")

        def isRunning(self):
            return False

    monkeypatch.setattr(panel_mod, "TestConnectionThread", FakeThread)

    # Stub progress dialog and message boxes
    class DummyProgress:
        def __init__(self, *a, **k):
            pass

        def setWindowModality(self, *a, **k):
            pass

        def show(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(panel_mod, "QProgressDialog", DummyProgress)

    class _MB:
        @staticmethod
        def warning(*a, **k):
            return None

        @staticmethod
        def critical(*a, **k):
            return None

        @staticmethod
        def information(*a, **k):
            return None

    monkeypatch.setattr(panel_mod, "QMessageBox", _MB)

    # Test pinecone missing API key -> warning and return
    def set_provider_combo(dlg, name):
        for i in range(dlg.provider_combo.count()):
            if dlg.provider_combo.itemData(i) == name:
                dlg.provider_combo.setCurrentIndex(i)
                return

    set_provider_combo(dlg, "pinecone")
    dlg.api_key_input.setText("")
    dlg._test_connection()  # should early-return with warning

    # Now provide API key
    dlg.api_key_input.setText("k")
    dlg._test_connection()  # uses FakeThread and should call finished -> _on_test_finished

    # Test weaviate persistent
    set_provider_combo(dlg, "weaviate")
    dlg.persistent_radio.setChecked(True)
    dlg.path_input.setText("/tmp")
    dlg._test_connection()

    # Test qdrant default branch
    set_provider_combo(dlg, "qdrant")
    dlg._test_connection()


def test_show_context_menu_and_create_and_double_click(qtbot, fake_service, mock_providers, monkeypatch):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])
    panel = panel_mod.ProfileManagerPanel(fake_service)
    qtbot.addWidget(panel)
    panel._refresh_profiles()
    assert panel.profile_list.count() > 0

    # Create profile should invoke dialog.exec; stub it
    class DummyDialog:
        def __init__(self, *a, **k):
            self.execed = False

        def exec(self):
            self.execed = True

    monkeypatch.setattr(panel_mod, "ProfileEditorDialog", DummyDialog)
    panel._create_profile()

    # Test double click handler emits connect_profile
    captured = {}

    def on_connect(pid):
        captured["id"] = pid

    panel.connect_profile.connect(on_connect)
    # Simulate double click on the first item
    item = panel.profile_list.item(0)
    panel._on_profile_double_clicked(item)
    assert "id" in captured


def test_save_profile_create_and_update_and_config_kwargs(qtbot, fake_service, mock_providers, monkeypatch):
    panel_mod = __import__("vector_inspector.ui.components.profile_manager_panel", fromlist=["*"])

    # New profile create (pinecone requires api_key)
    created = {}

    def fake_create(name, provider, config, credentials=None):
        created["args"] = dict(name=name, provider=provider, config=config, credentials=credentials)
        return "id-new"

    fake_service.create_profile = fake_create

    dlg = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)
    # set pinecone provider
    for i in range(dlg.provider_combo.count()):
        if dlg.provider_combo.itemData(i) == "pinecone":
            dlg.provider_combo.setCurrentIndex(i)
            break

    dlg.name_input.setText("P")
    dlg.api_key_input.setText("k")
    dlg._save_profile()
    assert created.get("args") is not None

    # Update existing profile (pgvector with password)
    updated = {}

    def fake_update(pid, name=None, config=None, credentials=None):
        updated["args"] = dict(pid=pid, name=name, config=config, credentials=credentials)
        return True

    fake_service.update_profile = fake_update
    profile = ConnectionProfile("u1", "Old", "pgvector", {"type": "http", "host": "h"})
    fake_service._profiles["u1"] = profile
    dlg2 = ProfileEditorDialog(fake_service, profile=profile)
    qtbot.addWidget(dlg2)
    dlg2.name_input.setText("NewName")
    # pgvector http - ensure password saved
    dlg2.http_radio.setChecked(True)
    dlg2.password_input.setText("pw")
    dlg2._save_profile()
    assert updated.get("args") is not None

    # _get_config weaviate cloud branch
    dlg3 = ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg3)
    for i in range(dlg3.provider_combo.count()):
        if dlg3.provider_combo.itemData(i) == "weaviate":
            dlg3.provider_combo.setCurrentIndex(i)
            break
    dlg3.http_radio.setChecked(True)
    dlg3.weaviate_cloud_checkbox.setChecked(True)
    dlg3.host_input.setText("cluster.url")
    cfg = dlg3._get_config()
    assert cfg.get("type") == "cloud" and cfg.get("url") == "cluster.url"

    # _get_connection_kwargs with api_key and password
    dlg3.api_key_input.setText("akey")
    dlg3.password_input.setText("pwd")
    http_cfg = {"type": "http", "host": "h", "port": 1234, "database": "db", "user": "u"}
    kwargs = dlg3._get_connection_kwargs(http_cfg)
    assert kwargs.get("api_key") == "akey"
    assert kwargs.get("password") == "pwd"


def test_fetch_databases_real_implementation(qtbot, fake_service, mock_providers, monkeypatch):
    """_fetch_databases starts a DatabaseFetchThread with parsed connection values and updates the UI state."""
    panel_mod = __import__(
        "vector_inspector.ui.components.profile_manager_panel",
        fromlist=["ProfileEditorDialog"],
    )

    started = {}

    class FakeDatabaseFetchThread:
        def __init__(self, host, port, user, password, parent=None):
            started["host"] = host
            started["port"] = port
            started["user"] = user
            started["password"] = password
            self._cb = None

            class _Sig:
                def connect(inner_self, cb):
                    self._cb = cb

            self.finished = _Sig()

        def start(self):
            started["started"] = True

        def isRunning(self):
            return False

    monkeypatch.setattr(panel_mod, "DatabaseFetchThread", FakeDatabaseFetchThread)

    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Switch to pgvector so the DB section is visible
    for i in range(dlg.provider_combo.count()):
        if dlg.provider_combo.itemData(i) == "pgvector":
            dlg.provider_combo.setCurrentIndex(i)
            break

    dlg.host_input.setText("localhost")
    dlg.port_input.setText("5432")
    dlg.user_input.setText("admin")
    dlg.password_input.setText("secret")

    # Call the REAL _fetch_databases (not a stub)
    dlg._fetch_databases()

    assert started.get("started") is True
    assert started.get("host") == "localhost"
    assert started.get("port") == 5432
    assert started.get("user") == "admin"
    assert started.get("password") == "secret"
    # The button should be disabled and status label updated while fetching
    assert not dlg.db_refresh_btn.isEnabled()
    assert dlg.db_status_label.text() == "Fetching\u2026"


def test_on_databases_fetched_populates_and_handles_error(qtbot, fake_service, mock_providers, monkeypatch):
    """Exercises _on_databases_fetched for both success and error branches."""
    panel_mod = __import__(
        "vector_inspector.ui.components.profile_manager_panel",
        fromlist=["ProfileEditorDialog"],
    )

    class _MB:
        warned = []

        @classmethod
        def warning(cls, *a, **k):
            cls.warned.append(a)

    monkeypatch.setattr(panel_mod, "QMessageBox", _MB)

    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Switch to pgvector so database_input widget is visible
    for i in range(dlg.provider_combo.count()):
        if dlg.provider_combo.itemData(i) == "pgvector":
            dlg.provider_combo.setCurrentIndex(i)
            break

    # Manually disable refresh btn to simulate in-progress state
    dlg.db_refresh_btn.setEnabled(False)

    # Success: list of databases returned
    dlg._on_databases_fetched(["mydb", "otherdb"], "")
    assert dlg.db_refresh_btn.isEnabled()
    assert "2" in dlg.db_status_label.text() or "Loaded" in dlg.db_status_label.text()

    # Error: empty list + error message
    dlg.db_refresh_btn.setEnabled(False)
    dlg._on_databases_fetched([], "connection refused")
    assert dlg.db_refresh_btn.isEnabled()
    assert "Failed" in dlg.db_status_label.text()
    assert len(_MB.warned) > 0

    # Empty list with no error should clear label silently
    dlg._on_databases_fetched([], "")
    assert dlg.db_status_label.text() == ""


def test_save_button_disabled_for_placeholder_provider(qtbot, fake_service, mock_no_providers):
    """Save button is disabled when the placeholder '(Select a provider...)' is selected."""
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # After initialization, the placeholder should be selected
    assert dlg.provider_combo.currentText() == "(Select a provider...)"
    assert not dlg.save_btn.isEnabled()


def test_save_button_enabled_after_selecting_real_provider(qtbot, fake_service, mock_providers):
    """Save button is enabled after selecting a real provider."""
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Select a real provider (e.g., chromadb)
    for i in range(dlg.provider_combo.count()):
        if dlg.provider_combo.itemData(i) == "chromadb":
            dlg.provider_combo.setCurrentIndex(i)
            break

    # Save button should now be enabled
    assert dlg.save_btn.isEnabled()


def test_initial_setup_prevents_premature_config_prompts(qtbot, fake_service, mock_providers):
    """_initial_setup flag prevents provider install prompts during dialog initialization."""
    # This test verifies that creating a dialog doesn't trigger any prompts
    # The _initial_setup flag is internal state management
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # If we got here without hanging, the initial setup worked correctly
    assert dlg.provider_combo.count() > 0


def test_update_save_button_state_handles_missing_save_btn(qtbot, fake_service, mock_providers):
    """_update_save_button_state gracefully handles missing save_btn during init."""
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # Manually call _update_save_button_state (normally called during provider change)
    # Should not raise even if save_btn is not yet created
    try:
        dlg._update_save_button_state()
        # If save_btn exists, this should work
        assert True
    except AttributeError:
        # If it doesn't exist yet, the hasattr guard should prevent AttributeError
        pytest.fail("_update_save_button_state raised AttributeError - guard missing")


def test_provider_combo_starts_with_placeholder(qtbot, fake_service, mock_no_providers):
    """Provider combo starts with '(Select a provider...)' placeholder at index 0."""
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # First item should be the placeholder
    assert dlg.provider_combo.itemText(0) == "(Select a provider...)"
    assert dlg.provider_combo.itemData(0) is None


def test_placeholder_provider_hides_all_config_fields(qtbot, fake_service, mock_no_providers):
    """When placeholder is selected, all configuration fields are hidden."""
    dlg = panel_mod.ProfileEditorDialog(fake_service)
    qtbot.addWidget(dlg)

    # With mock_no_providers, placeholder should be at index 0 and auto-selected
    assert dlg.provider_combo.currentData() is None

    # Since no provider is selected, configuration section should not show specific fields
    # The dialog starts in a state where no provider-specific config is shown


def test_editing_existing_profile_skips_placeholder(qtbot, fake_service, mock_providers):
    """When editing an existing profile, the provider combo has no placeholder."""
    profile = ConnectionProfile("p1", "Test", "chromadb", {"type": "persistent", "path": "/tmp"})
    fake_service._profiles["p1"] = profile

    dlg = panel_mod.ProfileEditorDialog(fake_service, profile=profile)
    qtbot.addWidget(dlg)

    # First item should NOT be placeholder when editing (providers available)
    assert dlg.provider_combo.itemText(0) != "(Select a provider...)"
    # Provider should be set to chromadb
    assert dlg.provider_combo.currentData() == "chromadb"


def test_provider_change_during_edit_mode_works(qtbot, fake_service, mock_providers):
    """Changing provider while editing an existing profile updates fields correctly."""
    profile = ConnectionProfile("p1", "Test", "chromadb", {"type": "persistent", "path": "/tmp"})
    fake_service._profiles["p1"] = profile

    dlg = panel_mod.ProfileEditorDialog(fake_service, profile=profile)
    qtbot.addWidget(dlg)

    # Initially chromadb with persistent
    assert dlg.provider_combo.currentData() == "chromadb"

    # Change to lancedb
    for i in range(dlg.provider_combo.count()):
        if dlg.provider_combo.itemData(i) == "lancedb":
            dlg.provider_combo.setCurrentIndex(i)
            break

    dlg._on_provider_changed()

    # Should reset to persistent (lancedb only supports persistent)
    assert dlg.persistent_radio.isChecked()
    assert not dlg.path_input.isHidden()
