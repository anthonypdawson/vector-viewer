import json
from unittest.mock import MagicMock, patch

from vector_inspector.services.backup_helpers import write_backup_zip
from vector_inspector.services.backup_restore_service import BackupRestoreService


def test_restore_uses_prepare_restore_and_adds_items(tmp_path, empty_fake_provider):
    """Test that restore creates collection and adds items using FakeProvider fixture."""
    metadata = {
        "collection_name": "col",
        "backup_timestamp": "now",
        "collection_info": {"vector_dimension": 3},
    }
    data = {
        "ids": ["1", "2"],
        "documents": ["a", "b"],
        "metadatas": [{}, {}],
        "embeddings": [[0, 0, 0], [1, 1, 1]],
    }
    p = tmp_path / "b.zip"
    write_backup_zip(p, metadata, data)

    conn = empty_fake_provider
    svc = BackupRestoreService()
    ok = svc.restore_collection(conn, str(p))
    assert ok is True
    # Verify collection was created and items were added
    assert "col" in conn.list_collections()
    items = conn.get_all_items("col")
    assert len(items["ids"]) == 2
    assert items["documents"] == ["a", "b"]


def test_restore_with_empty_embeddings(tmp_path, empty_fake_provider):
    """Test restore with empty embeddings list using FakeProvider fixture."""
    metadata = {
        "collection_name": "col_empty",
        "backup_timestamp": "now",
        "collection_info": {"vector_dimension": 3},
    }
    data = {"ids": ["1", "2"], "documents": ["a", "b"], "metadatas": [{}, {}], "embeddings": []}
    p = tmp_path / "b_empty.zip"
    write_backup_zip(p, metadata, data)

    conn = empty_fake_provider
    svc = BackupRestoreService()
    ok = svc.restore_collection(conn, str(p))
    assert ok is True
    # Verify collection was created and items were added
    assert "col_empty" in conn.list_collections()
    items = conn.get_all_items("col_empty")
    assert len(items["ids"]) == 2


def test_backup_includes_model_from_settings(tmp_path, fake_provider):
    """Test that backup includes model config from app settings."""
    conn = fake_provider
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


def test_restore_persists_model_to_settings(tmp_path, empty_fake_provider):
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

    conn = empty_fake_provider
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


def test_backup_and_restore_roundtrip(tmp_path, fake_provider_with_name):
    """Test complete backup and restore cycle with FakeProvider."""
    conn, collection_name = fake_provider_with_name
    svc = BackupRestoreService()

    # Backup the collection
    backup_path = svc.backup_collection(
        conn,
        collection_name,
        str(tmp_path),
        include_embeddings=True,
    )
    assert backup_path is not None

    # Verify original data
    original = conn.get_all_items(collection_name)
    assert len(original["ids"]) == 3

    # Delete the collection
    conn.delete_collection(collection_name)
    assert collection_name not in conn.list_collections()

    # Restore from backup
    ok = svc.restore_collection(conn, backup_path)
    assert ok is True
    assert collection_name in conn.list_collections()

    # Verify restored data matches original
    restored = conn.get_all_items(collection_name)
    assert len(restored["ids"]) == len(original["ids"])
    assert restored["documents"] == original["documents"]
