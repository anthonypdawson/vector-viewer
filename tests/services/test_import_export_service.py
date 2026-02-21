"""Tests for ImportExportService using FakeProvider."""

import json

import pandas as pd

from vector_inspector.services.import_export_service import ImportExportService


def test_export_to_json(tmp_path, fake_provider_with_name):
    """Test exporting collection data to JSON format."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    # Get data from FakeProvider
    data = conn.get_all_items(collection_name)

    # Export to JSON
    json_path = tmp_path / "export.json"
    success = svc.export_to_json(data, str(json_path))
    assert success is True
    assert json_path.exists()

    # Verify content
    with open(json_path) as f:
        exported = json.load(f)

    assert len(exported) == 3
    assert exported[0]["id"] in data["ids"]
    assert exported[0]["document"] in data["documents"]
    assert "metadata" in exported[0]
    assert "embedding" in exported[0]


def test_export_to_csv_without_embeddings(tmp_path, fake_provider_with_name):
    """Test exporting collection data to CSV without embeddings."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    data = conn.get_all_items(collection_name)

    # Export to CSV without embeddings
    csv_path = tmp_path / "export.csv"
    success = svc.export_to_csv(data, str(csv_path), include_embeddings=False)
    assert success is True
    assert csv_path.exists()

    # Verify content
    df = pd.read_csv(csv_path)
    assert len(df) == 3
    assert "id" in df.columns
    assert "document" in df.columns
    assert "embedding" not in df.columns
    # Check metadata columns
    assert any(col.startswith("metadata_") for col in df.columns)


def test_export_to_csv_with_embeddings(tmp_path, fake_provider_with_name):
    """Test exporting collection data to CSV with embeddings."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    data = conn.get_all_items(collection_name)

    # Export to CSV with embeddings
    csv_path = tmp_path / "export_emb.csv"
    success = svc.export_to_csv(data, str(csv_path), include_embeddings=True)
    assert success is True

    # Verify content
    df = pd.read_csv(csv_path)
    assert "embedding" in df.columns
    # Embeddings should be JSON-encoded strings
    emb = json.loads(df["embedding"].iloc[0])
    assert isinstance(emb, list)


def test_export_to_parquet(tmp_path, fake_provider_with_name):
    """Test exporting collection data to Parquet format."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    data = conn.get_all_items(collection_name)

    # Export to Parquet
    parquet_path = tmp_path / "export.parquet"
    success = svc.export_to_parquet(data, str(parquet_path))
    assert success is True
    assert parquet_path.exists()

    # Verify content
    df = pd.read_parquet(parquet_path)
    assert len(df) == 3
    assert "id" in df.columns
    assert "document" in df.columns
    assert "embedding" in df.columns


def test_import_from_json(tmp_path, fake_provider):
    """Test importing collection data from JSON format."""
    svc = ImportExportService()

    # Create sample JSON file
    sample_data = [
        {"id": "1", "document": "test1", "metadata": {"type": "a"}, "embedding": [0.1, 0.2]},
        {"id": "2", "document": "test2", "metadata": {"type": "b"}, "embedding": [0.3, 0.4]},
    ]

    json_path = tmp_path / "import.json"
    with open(json_path, "w") as f:
        json.dump(sample_data, f)

    # Import from JSON
    result = svc.import_from_json(str(json_path))
    assert result is not None
    assert len(result["ids"]) == 2
    assert result["ids"] == ["1", "2"]
    assert result["documents"] == ["test1", "test2"]
    assert len(result["metadatas"]) == 2
    assert result["metadatas"][0]["type"] == "a"
    assert len(result["embeddings"]) == 2


def test_import_from_csv(tmp_path):
    """Test importing collection data from CSV format."""
    svc = ImportExportService()

    # Create sample CSV file
    df = pd.DataFrame(
        {
            "id": ["1", "2"],
            "document": ["test1", "test2"],
            "metadata_type": ["a", "b"],
            "embedding": ["[0.1, 0.2]", "[0.3, 0.4]"],
        }
    )

    csv_path = tmp_path / "import.csv"
    df.to_csv(csv_path, index=False)

    # Import from CSV
    result = svc.import_from_csv(str(csv_path))
    assert result is not None
    assert len(result["ids"]) == 2
    assert result["documents"] == ["test1", "test2"]
    assert result["metadatas"][0]["type"] == "a"
    assert len(result["embeddings"]) == 2
    assert result["embeddings"][0] == [0.1, 0.2]


def test_import_from_parquet(tmp_path):
    """Test importing collection data from Parquet format."""
    svc = ImportExportService()

    # Create sample Parquet file
    df = pd.DataFrame(
        {
            "id": ["1", "2"],
            "document": ["test1", "test2"],
            "metadata_type": ["a", "b"],
            "embedding": [[0.1, 0.2], [0.3, 0.4]],
        }
    )

    parquet_path = tmp_path / "import.parquet"
    df.to_parquet(parquet_path, index=False)

    # Import from Parquet
    result = svc.import_from_parquet(str(parquet_path))
    assert result is not None
    assert len(result["ids"]) == 2
    assert result["documents"] == ["test1", "test2"]
    assert result["metadatas"][0]["type"] == "a"
    assert len(result["embeddings"]) == 2


def test_export_import_roundtrip_json(tmp_path, fake_provider_with_name):
    """Test that export then import preserves data (JSON)."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    # Export original data
    original_data = conn.get_all_items(collection_name)
    json_path = tmp_path / "roundtrip.json"
    svc.export_to_json(original_data, str(json_path))

    # Import it back
    imported = svc.import_from_json(str(json_path))

    # Verify data is preserved
    assert len(imported["ids"]) == len(original_data["ids"])
    assert set(imported["ids"]) == set(original_data["ids"])
    assert len(imported["embeddings"]) == len(original_data["embeddings"])


def test_export_import_roundtrip_parquet(tmp_path, fake_provider_with_name):
    """Test that export then import preserves data (Parquet)."""
    conn, collection_name = fake_provider_with_name
    svc = ImportExportService()

    # Export original data
    original_data = conn.get_all_items(collection_name)
    parquet_path = tmp_path / "roundtrip.parquet"
    svc.export_to_parquet(original_data, str(parquet_path))

    # Import it back
    imported = svc.import_from_parquet(str(parquet_path))

    # Verify data is preserved
    assert len(imported["ids"]) == len(original_data["ids"])
    assert set(imported["ids"]) == set(original_data["ids"])


def test_import_and_add_to_provider(tmp_path, empty_fake_provider):
    """Test importing data and adding it to a FakeProvider collection."""
    conn = empty_fake_provider
    svc = ImportExportService()

    # Create sample JSON
    sample_data = [
        {
            "id": "1",
            "document": "imported1",
            "metadata": {"source": "import"},
            "embedding": [1.0, 0.0],
        },
        {
            "id": "2",
            "document": "imported2",
            "metadata": {"source": "import"},
            "embedding": [0.0, 1.0],
        },
    ]

    json_path = tmp_path / "import.json"
    with open(json_path, "w") as f:
        json.dump(sample_data, f)

    # Import from JSON
    data = svc.import_from_json(str(json_path))

    # Add to FakeProvider
    conn.create_collection(
        "imported_collection",
        data["documents"],  # docs (positional)
        data["metadatas"],  # metadatas
        data["embeddings"],  # embeddings
        data["ids"],  # ids
    )

    # Verify collection was created
    assert "imported_collection" in conn.list_collections()
    items = conn.get_all_items("imported_collection")
    assert len(items["ids"]) == 2
    assert items["documents"] == ["imported1", "imported2"]
    assert items["metadatas"][0]["source"] == "import"
