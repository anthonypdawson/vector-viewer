def make_fake_connection(return_info=None, raise_exc=False):
    class Fake:
        def __init__(self):
            self.is_connected = True
            self.id = "fake-db"
            self.name = "fake"

        def get_collection_info(self, name):
            if raise_exc:
                raise RuntimeError("boom")
            return return_info

        def get_embedding_model(self, coll):
            return None

        def list_collections(self):
            return ["a", "b"]

    return Fake()


def make_fake_app_state():
    class S:
        def __init__(self):
            self.provider = None
            self.cache_manager = type(
                "C",
                (),
                {"get": lambda *a, **k: None, "invalidate": lambda *a, **k: None, "update": lambda *a, **k: None},
            )()
            self.database = "conn-id"

            # simple signals
            class Sig:
                def connect(self, fn):
                    pass

            self.provider_changed = Sig()
            self.collection_changed = Sig()

    return S()


def test_model_config_thread_success(monkeypatch):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    conn = make_fake_connection(return_info={"vector_dimension": 128})
    t = mod.ModelConfigPreparationThread(conn, "coll")

    captured = {}

    def on_finished(info):
        captured["info"] = info

    t.finished.connect(on_finished)
    # run synchronously
    t.run()
    assert "info" in captured


def test_model_config_thread_error(monkeypatch):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    conn = make_fake_connection(raise_exc=True)
    t = mod.ModelConfigPreparationThread(conn, "coll")

    captured = {}

    def on_error(msg):
        captured["err"] = msg

    t.error.connect(on_error)
    t.run()
    assert "err" in captured


def test_refresh_database_info_no_connection(qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)
    # Ensure no provider
    panel.connection = None
    panel.refresh_database_info()
    # Labels should show not connected values
    assert "Not connected" in panel.provider_label.property("value_label").text()


def test_refresh_database_info_with_backend(qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    fake = make_fake_connection(return_info={"vector_dimension": 64})
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)
    panel.connection = fake
    panel.refresh_database_info()
    # collections count should update
    assert panel.collections_count_label.property("value_label").text() in ("2",)


def test_display_collection_info_provider_variants(qtbot, monkeypatch):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)

    # Chroma-like backend
    class Chroma:
        pass

    panel.connection = type(
        "CI",
        (),
        {
            "database": Chroma(),
            "is_connected": True,
            "name": "c",
            "id": "cid",
            "get_embedding_model": lambda self, coll: None,
        },
    )()
    info = {"vector_dimension": 32, "metadata_fields": ["a", "b"], "count": 10}
    panel.current_collection = "coll"
    panel._display_collection_info(info)
    assert "No metadata fields" not in panel.schema_label.text()


def test_set_collection_cache_hit(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()

    # fake cached object
    class Cached:
        def __init__(self, data):
            self.user_inputs = {"collection_info": data}

    cache = type(
        "C",
        (),
        {
            "get": staticmethod(lambda a, b: Cached({"vector_dimension": 16, "metadata_fields": []})),
            "invalidate": lambda *a, **k: None,
            "update": lambda *a, **k: None,
        },
    )()
    app_state.cache_manager = cache
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)
    panel.set_collection("coll", "dbid")
    # Should have set current_collection and shown auto-detect or similar
    assert panel.current_collection == "coll"


def test_refresh_collection_info_uses_thread(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)

    # fake connection
    fake_conn = make_fake_connection(return_info={"vector_dimension": 8})
    panel.connection = fake_conn
    panel.current_collection = "coll"

    # Replace CollectionInfoLoadThread with one that immediately emits finished
    class Emittable:
        def __init__(self):
            self._cb = None

        def connect(self, cb):
            self._cb = cb

        def emit(self, *a, **k):
            if self._cb:
                self._cb(*a, **k)

    class FakeLoad:
        def __init__(self, connection, collection_name, parent=None):
            self.finished = Emittable()
            self.error = Emittable()

        def start(self):
            try:
                self.finished.emit({"vector_dimension": 8, "metadata_fields": []})
            except Exception:
                pass

    monkeypatch.setattr(mod, "CollectionInfoLoadThread", FakeLoad)
    panel.refresh_collection_info()
    assert panel.collection_info_thread is not None


def test_update_embedding_model_display_variants(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)

    # Case 1: embedding_model present in collection_info
    ci = {"embedding_model": "m1", "embedding_model_type": "stored"}
    panel._update_embedding_model_display(ci)
    assert "m1 (stored)" in panel.embedding_model_label.text()
    assert panel.clear_embedding_btn.isEnabled()

    # Case 2: connection can detect model
    panel.connection = type(
        "C", (), {"get_embedding_model": lambda self, c: "detected-model", "name": "x", "id": "cid"}
    )()
    panel.current_collection = "coll"
    panel._update_embedding_model_display({})
    assert "detected" in panel.embedding_model_label.text()

    # Case 3: SettingsService provides model
    class DummySettings:
        def get_embedding_model(self, profile, coll):
            return {"model": "smod", "type": "user"}

    monkeypatch.setattr("vector_inspector.services.settings_service.SettingsService", DummySettings)
    panel.connection = type("C2", (), {"name": "p", "id": "cid", "get_embedding_model": lambda self, c: None})()
    panel.current_collection = "coll"
    panel._update_embedding_model_display({})
    assert "smod" in panel.embedding_model_label.text()


def test_clear_embedding_model_and_update_state(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    # make cache manager spy
    invocations = {}
    cache = type(
        "C",
        (),
        {
            "get": lambda *a, **k: None,
            "invalidate": lambda *a, **k: invocations.setdefault("invalidated", (a[0], a[1]) if len(a) >= 2 else a),
            "update": lambda *a, **k: None,
        },
    )()
    app_state.cache_manager = cache
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)
    panel.connection = type("Conn", (), {"id": "cid", "name": "p", "is_connected": True})()
    panel.current_collection = "coll"

    # stub SettingsService methods
    class Svc:
        def remove_embedding_model(self, profile, coll):
            invocations.setdefault("removed", (profile, coll))

    monkeypatch.setattr("vector_inspector.services.settings_service.SettingsService", Svc)
    panel._clear_embedding_model()
    assert invocations.get("removed") == ("p", "coll")
    assert invocations.get("invalidated") is not None


def test_configure_embedding_model_flow(monkeypatch, qtbot):
    mod = __import__("vector_inspector.ui.views.info_panel", fromlist=["*"])
    app_state = make_fake_app_state()
    # Prepare panel
    panel = mod.InfoPanel(app_state, None)
    qtbot.addWidget(panel)
    panel.connection = type("Conn", (), {"id": "cid", "name": "p", "get_embedding_model": lambda self, c: None})()
    panel.current_collection = "coll"

    # Fake LoadingDialog to avoid UI
    class FakeLoading:
        def __init__(self, *a, **k):
            pass

        def show_loading(self, *a, **k):
            pass

        def hide_loading(self):
            pass

    monkeypatch.setattr("vector_inspector.ui.views.info_panel.LoadingDialog", FakeLoading)

    # Fake ModelConfigPreparationThread to immediately call finished
    class Emittable:
        def __init__(self):
            self._cb = None

        def connect(self, cb):
            self._cb = cb

        def emit(self, *a, **k):
            if self._cb:
                self._cb(*a, **k)

    class FakeModelThread:
        def __init__(self, connection, collection_name, parent=None):
            self.finished = Emittable()
            self.error = Emittable()

        def start(self):
            self.finished.emit({"vector_dimension": 32})

    monkeypatch.setattr(mod, "ModelConfigPreparationThread", FakeModelThread)

    # Stub dialogs: ProviderTypeDialog and EmbeddingConfigDialog
    class PTD:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1  # Accepted

        def get_selected_type(self):
            return "stored"

    class ECD:
        def __init__(self, *a, **k):
            pass

        def exec(self):
            return 1

        def get_selection(self):
            return ("mymodel", "stored")

    monkeypatch.setattr("vector_inspector.ui.views.info_panel.ProviderTypeDialog", PTD)
    monkeypatch.setattr("vector_inspector.ui.views.info_panel.EmbeddingConfigDialog", ECD)

    # Stub SettingsService.save_embedding_model and cache invalidation
    saved = {}

    class Svc2:
        def save_embedding_model(self, profile, coll, model, mtype):
            saved["args"] = (profile, coll, model, mtype)

    monkeypatch.setattr("vector_inspector.services.settings_service.SettingsService", Svc2)
    panel.cache_manager = type("C", (), {"invalidate": lambda *a, **k: saved.setdefault("invalidated", True)})()

    panel._configure_embedding_model()
    assert saved.get("args") == ("p", "coll", "mymodel", "stored")
