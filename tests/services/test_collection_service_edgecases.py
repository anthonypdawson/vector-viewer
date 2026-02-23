import uuid

import numpy as np

from vector_inspector.core.sample_data import SampleDataType
from vector_inspector.services.collection_service import CollectionService


class _FakeConnectionBase:
    def __init__(self, create_success=True, add_success=True, profile_name=None, cls_name="MockDB"):
        self._create_success = create_success
        self._add_success = add_success
        self.profile_name = profile_name

    def create_collection(self, **kwargs):
        return self._create_success

    def add_items(self, **kwargs):
        return self._add_success


def FakeConnection(create_success=True, add_success=True, profile_name=None, cls_name="MockDB"):
    C = type(cls_name, (_FakeConnectionBase,), {})
    return C(create_success=create_success, add_success=add_success, profile_name=profile_name)


class ProviderBase:
    def __init__(self, dimension=4, encode_success=True, return_numpy=False, bad_shape=False):
        self.dimension = dimension
        self._encode_success = encode_success
        self._return_numpy = return_numpy
        self._bad_shape = bad_shape

    def get_metadata(self):
        class M:
            dimension = self.dimension

        return M()

    def encode(self, texts, normalize=True, show_progress=False):
        if not self._encode_success:
            raise RuntimeError("encode-failed")
        n = len(texts)
        if self._bad_shape:
            # return wrong inner length
            arr = np.zeros((n, self.dimension + 1))
        else:
            arr = np.zeros((n, self.dimension))
        if self._return_numpy:
            return arr
        return arr.tolist()


def test_weaviate_ids_are_uuids(monkeypatch):
    svc = CollectionService()

    # provider that returns list embeddings
    monkeypatch.setattr(
        "vector_inspector.services.collection_service.ProviderFactory.create",
        staticmethod(lambda n, t: ProviderBase(dimension=3)),
    )

    captured = {}

    class WeaviateConn(FakeConnection(add_success=True, cls_name="WeaviateMock").__class__):
        def add_items(self, collection_name, documents, metadatas, ids, embeddings):
            captured["ids"] = ids
            return True

    conn = WeaviateConn()
    success, msg = svc.populate_with_sample_data(conn, "colW", 2, SampleDataType.TEXT, "m")
    assert success is True
    assert "ids" in captured
    # ensure ids are UUIDs
    for _id in captured["ids"]:
        uuid.UUID(_id)


def test_numpy_embeddings_converted_to_list(monkeypatch):
    svc = CollectionService()

    monkeypatch.setattr(
        "vector_inspector.services.collection_service.ProviderFactory.create",
        staticmethod(lambda n, t: ProviderBase(dimension=5, return_numpy=True)),
    )

    captured = {}

    class Conn(FakeConnection(add_success=True).__class__):
        def add_items(self, collection_name, documents, metadatas, ids, embeddings):
            captured["embeddings_type"] = type(embeddings)
            captured["inner_len"] = len(embeddings[0])
            return True

    conn = Conn()
    success, msg = svc.populate_with_sample_data(conn, "colN", 3, SampleDataType.TEXT, "m")
    assert success is True
    assert captured["embeddings_type"] is list
    assert captured["inner_len"] == 5


def test_encode_bad_shape_causes_failure(monkeypatch):
    svc = CollectionService()

    monkeypatch.setattr(
        "vector_inspector.services.collection_service.ProviderFactory.create",
        staticmethod(lambda n, t: ProviderBase(dimension=4, bad_shape=True)),
    )

    class Conn(FakeConnection(add_success=True).__class__):
        def add_items(self, **kwargs):
            # Check inner len mismatch and raise
            embeddings = kwargs.get("embeddings")
            inner_len = len(embeddings[0])
            if inner_len != 4:
                raise ValueError("bad-dim")
            return True

    conn = Conn()
    success, msg = svc.populate_with_sample_data(conn, "colB", 2, SampleDataType.TEXT, "m")
    assert success is False
    assert "Failed to insert data" in msg or "Failed to" in msg


def test_settings_save_failure_does_not_fail_operation(monkeypatch):
    svc = CollectionService()

    monkeypatch.setattr(
        "vector_inspector.services.collection_service.ProviderFactory.create",
        staticmethod(lambda n, t: ProviderBase(dimension=4)),
    )

    # Patch SettingsService to raise on save
    import vector_inspector.services.settings_service as settings_mod

    class BadSettings:
        def save_embedding_model(self, *args, **kwargs):
            raise RuntimeError("save-failed")

    monkeypatch.setattr(settings_mod, "SettingsService", BadSettings)

    conn = FakeConnection(add_success=True)
    success, msg = svc.populate_with_sample_data(conn, "colS", 2, SampleDataType.TEXT, "m")
    assert success is True


def test_signals_emitted_in_sequence(monkeypatch):
    svc = CollectionService()

    monkeypatch.setattr(
        "vector_inspector.services.collection_service.ProviderFactory.create",
        staticmethod(lambda n, t: ProviderBase(dimension=4)),
    )

    seq = []

    def on_started(name):
        seq.append(("started", name))

    def on_progress(msg, cur, tot):
        seq.append(("progress", msg, cur, tot))

    def on_completed(name, success, message):
        seq.append(("completed", name, success))

    svc.operation_started.connect(on_started)
    svc.operation_progress.connect(on_progress)
    svc.operation_completed.connect(on_completed)

    conn = FakeConnection(add_success=True)
    success, msg = svc.populate_with_sample_data(conn, "colSig", 2, SampleDataType.TEXT, "m")
    assert success is True
    # basic checks for recorded sequences
    assert any(s[0] == "started" for s in seq)
    assert any(s[0] == "completed" for s in seq)
