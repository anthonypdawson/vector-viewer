import json
from unittest.mock import MagicMock, patch

from vector_inspector.services.backup_helpers import write_backup_zip
from vector_inspector.services.backup_restore_service import BackupRestoreService


class FakeConnection:
    def __init__(self):
        self.collections = []
        self.added = None

    def list_collections(self):
        return self.collections

    def delete_collection(self, name):
        if name in self.collections:
            self.collections.remove(name)

    def prepare_restore(self, metadata, data):
        # Pretend to precreate collection
        self.collections.append(metadata.get("collection_name"))
        # Ensure IDs are strings
        if data.get("ids"):
            data["ids"] = [str(i) for i in data.get("ids")]
        return True

    def add_items(self, collection_name, documents, metadatas, ids, embeddings):
        self.added = dict(
            collection_name=collection_name,
            documents=documents,
            metadatas=metadatas,
            ids=ids,
            embeddings=embeddings,
        )
        return True


def test_restore_uses_prepare_restore_and_adds_items(tmp_path):
    metadata = {
        "collection_name": "col",
        "backup_timestamp": "now",
        "collection_info": {"vector_dimension": 3},
    }
    data = {
        "ids": [1, 2],
        "documents": ["a", "b"],
        "metadatas": [{}, {}],
        "embeddings": [[0, 0, 0], [1, 1, 1]],
    }
    p = tmp_path / "b.zip"
    write_backup_zip(p, metadata, data)

    conn = FakeConnection()
    svc = BackupRestoreService()
    ok = svc.restore_collection(conn, str(p))
    assert ok is True
    assert conn.added is not None
    assert conn.added["collection_name"] == "col"
    assert conn.added["ids"] == ["1", "2"]


def test_restore_with_empty_embeddings_triggers_prepare_restore(tmp_path):
    # Prepare a backup where embeddings key exists but is an empty list
    metadata = {
        "collection_name": "col_empty",
        "backup_timestamp": "now",
        "collection_info": {"vector_dimension": 3},
    }
    data = {"ids": [1, 2], "documents": ["a", "b"], "metadatas": [{}, {}], "embeddings": []}
    p = tmp_path / "b_empty.zip"
    write_backup_zip(p, metadata, data)

    class FakeConn2:
        def __init__(self):
            self.collections = []
            self.added = None

        def list_collections(self):
            return self.collections

        def delete_collection(self, name):
            if name in self.collections:
                self.collections.remove(name)

        def prepare_restore(self, metadata, data):
            # Simulate provider generating embeddings when list is empty
            if data.get("embeddings") == []:
                data["embeddings"] = [[0.0, 0.0, 0.0], [1.0, 1.0, 1.0]]
            self.collections.append(metadata.get("collection_name"))
            return True

        def add_items(self, collection_name, documents, metadatas, ids, embeddings):
            self.added = dict(
                collection_name=collection_name,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                embeddings=embeddings,
            )
            return True

    conn = FakeConn2()
    svc = BackupRestoreService()
    ok = svc.restore_collection(conn, str(p))
    assert ok is True
    assert conn.added is not None
    assert conn.added["collection_name"] == "col_empty"
    assert conn.added["embeddings"] is not None
    assert len(conn.added["embeddings"]) == 2


def test_backup_includes_model_from_settings(tmp_path):
    """Test that backup includes model config from app settings when not in collection info."""

    class FakeConnWithCollection:
        def get_collection_info(self, name):
            # Return collection info without model config
            return {"name": name, "count": 2}

        def get_all_items(self, name):
            return {
                "ids": ["1", "2"],
                "documents": ["test1", "test2"],
                "metadatas": [{}, {}],
                "embeddings": [[0.1, 0.2], [0.3, 0.4]],
            }

        def get_embedding_model(self, name):
            # Simulate connection not having model info
            return None

    conn = FakeConnWithCollection()
    svc = BackupRestoreService()

    # Mock SettingsService to return a model config
    mock_settings = MagicMock()
    mock_settings.get_embedding_model.return_value = {
        "model": "sentence-transformers/all-MiniLM-L6-v2",
        "type": "sentence-transformer",
    }

    with patch(
        "vector_inspector.services.settings_service.SettingsService",
        return_value=mock_settings,
    ):
        backup_path = svc.backup_collection(
            conn,
            "test_collection",
            str(tmp_path),
            include_embeddings=True,
            profile_name="test_conn_id",
        )

    assert backup_path is not None

    # Verify the backup contains model config
    import zipfile

    with zipfile.ZipFile(backup_path, "r") as zf:
        metadata_json = zf.read("metadata.json")
        metadata = json.loads(metadata_json)

    assert metadata.get("embedding_model") == "sentence-transformers/all-MiniLM-L6-v2"
    assert metadata.get("embedding_model_type") == "sentence-transformer"


def test_restore_persists_model_to_settings(tmp_path):
    """Test that restore saves model config to app settings."""

    # Create a backup with model metadata
    metadata = {
        "collection_name": "restored_col",
        "backup_timestamp": "now",
        "collection_info": {"vector_dimension": 2},
        "embedding_model": "sentence-transformers/paraphrase-MiniLM-L6-v2",
        "embedding_model_type": "sentence-transformer",
    }
    data = {
        "ids": ["1", "2"],
        "documents": ["test1", "test2"],
        "metadatas": [{}, {}],
        "embeddings": [[0.1, 0.2], [0.3, 0.4]],
    }
    backup_file = tmp_path / "test_backup.zip"
    write_backup_zip(backup_file, metadata, data)

    conn = FakeConnection()
    svc = BackupRestoreService()

    # Mock SettingsService
    mock_settings = MagicMock()

    with patch(
        "vector_inspector.services.settings_service.SettingsService",
        return_value=mock_settings,
    ):
        ok = svc.restore_collection(
            conn,
            str(backup_file),
            profile_name="restored_conn_id",
        )

    assert ok is True

    # Verify that save_embedding_model was called with correct parameters
    mock_settings.save_embedding_model.assert_called_once_with(
        "restored_conn_id",
        "restored_col",
        "sentence-transformers/paraphrase-MiniLM-L6-v2",
        "sentence-transformer",
    )
