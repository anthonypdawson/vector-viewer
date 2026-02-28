"""Tests for CollectionCreationWorker (collection_worker module)."""

from PySide6.QtCore import QObject, Signal

import vector_inspector.ui.workers.collection_worker as cw_module
from vector_inspector.ui.workers.collection_worker import CollectionCreationWorker


class FakeConnection:
    """Minimal connection stub for worker tests."""

    profile_name = "test"


class FakeCollectionService(QObject):
    """Fake CollectionService that exposes required signals and methods."""

    operation_progress = Signal(str, int, int)

    def create_collection(self, connection, collection_name, dimension):
        return True

    def populate_with_sample_data(
        self, connection, collection_name, count, data_type, embedder_name, embedder_type, randomize=True
    ):
        return True, "Sample data added"


class FailingCollectionService(QObject):
    operation_progress = Signal(str, int, int)

    def create_collection(self, connection, collection_name, dimension):
        return False


class ExceptionCollectionService(QObject):
    operation_progress = Signal(str, int, int)

    def create_collection(self, connection, collection_name, dimension):
        raise RuntimeError("DB error")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_worker_emits_creation_complete_true_without_sample(qtbot, monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FakeCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="my_col",
        dimension=128,
        add_sample=False,
    )

    with qtbot.waitSignal(worker.creation_complete, timeout=5000) as blocker:
        worker.start()

    success, msg = blocker.args
    assert success is True
    assert "my_col" in msg


def test_worker_emits_creation_complete_false_on_service_failure(qtbot, monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FailingCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="fail_col",
        dimension=64,
        add_sample=False,
    )

    with qtbot.waitSignal(worker.creation_complete, timeout=5000) as blocker:
        worker.start()

    success, msg = blocker.args
    assert success is False


def test_worker_emits_error_on_exception(qtbot, monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", ExceptionCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="exc_col",
        dimension=32,
        add_sample=False,
    )

    with qtbot.waitSignal(worker.error_occurred, timeout=5000) as blocker:
        worker.start()

    assert "DB error" in blocker.args[0]


def test_worker_with_sample_data_emits_complete(qtbot, monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FakeCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    sample_config = {
        "count": 5,
        "data_type": "text",
        "embedder_name": "mock-embedder",
        "embedder_type": "sentence-transformer",
        "random_data": True,
    }

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="sample_col",
        dimension=128,
        add_sample=True,
        sample_config=sample_config,
    )

    with qtbot.waitSignal(worker.creation_complete, timeout=5000) as blocker:
        worker.start()

    success, _ = blocker.args
    assert success is True


# ---------------------------------------------------------------------------
# Direct run() call tests for coverage
# ---------------------------------------------------------------------------


def test_worker_run_direct_no_sample(monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FakeCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="col_direct",
        dimension=64,
        add_sample=False,
    )

    completed = []
    worker.creation_complete.connect(lambda s, m: completed.append((s, m)))
    worker.run()

    assert completed and completed[0][0] is True
    assert "col_direct" in completed[0][1]


def test_worker_run_direct_create_fails(monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FailingCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="fail_col",
        dimension=32,
        add_sample=False,
    )

    completed = []
    worker.creation_complete.connect(lambda s, m: completed.append((s, m)))
    worker.run()

    assert completed and completed[0][0] is False


def test_worker_run_direct_exception(monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", ExceptionCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="exc_col",
        dimension=16,
        add_sample=False,
    )

    errors = []
    worker.error_occurred.connect(lambda e: errors.append(e))
    worker.run()

    assert errors and "DB error" in errors[0]


def test_worker_run_direct_with_sample(monkeypatch):
    monkeypatch.setattr(cw_module, "CollectionService", FakeCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="sample_direct",
        dimension=128,
        add_sample=True,
        sample_config={
            "count": 3,
            "data_type": "text",
            "embedder_name": "mock",
            "embedder_type": "sentence-transformer",
        },
    )

    completed = []
    worker.creation_complete.connect(lambda s, m: completed.append((s, m)))
    worker.run()

    assert completed and completed[0][0] is True


class SampleFailingCollectionService(QObject):
    """Service where create_collection succeeds but populate_with_sample_data fails."""

    operation_progress = Signal(str, int, int)

    def create_collection(self, connection, collection_name, dimension):
        return True

    def populate_with_sample_data(
        self, connection, collection_name, count, data_type, embedder_name, embedder_type, randomize=True
    ):
        return False, "sample creation failed"


def test_worker_run_direct_sample_fails(monkeypatch):
    """sample creation fails after collection created."""
    monkeypatch.setattr(cw_module, "CollectionService", SampleFailingCollectionService)
    monkeypatch.setattr(cw_module, "TelemetryService", lambda: None)

    worker = CollectionCreationWorker(
        connection=FakeConnection(),
        collection_name="sample_fail_col",
        dimension=128,
        add_sample=True,
        sample_config={
            "count": 3,
            "data_type": "text",
            "embedder_name": "mock",
            "embedder_type": "sentence-transformer",
        },
    )

    completed = []
    worker.creation_complete.connect(lambda s, m: completed.append((s, m)))
    worker.run()

    assert completed
    success, msg = completed[0]
    assert success is False
    assert "sample" in msg.lower() or "failed" in msg.lower()
