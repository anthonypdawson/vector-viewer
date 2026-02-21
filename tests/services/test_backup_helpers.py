import json
from pathlib import Path

from vector_inspector.services.backup_helpers import write_backup_zip, read_backup_zip, normalize_embeddings


def test_write_and_read_backup_zip(tmp_path):
    metadata = {"collection_name": "col", "backup_timestamp": "now"}
    data = {"ids": ["1", "2"], "documents": ["a", "b"]}
    p = tmp_path / "test_backup.zip"
    write_backup_zip(p, metadata, data)

    read_meta, read_data = read_backup_zip(p)
    assert read_meta["collection_name"] == "col"
    assert read_data["ids"] == ["1", "2"]


def test_normalize_embeddings_list_of_lists():
    data = {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}
    out = normalize_embeddings(data)
    assert isinstance(out["embeddings"], list)
    assert out["embeddings"][0][0] == 0.1
