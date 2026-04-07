"""Integration tests for multimodal (image + document) sequential ingestion.

These tests verify:
- Images and documents can be ingested sequentially into the same collection.
- Image embeddings are 512-dim (CLIP) and doc embeddings are 384-dim (MiniLM).
- Both result items carry file-path metadata that allows preview detection.
- find_preview_paths() correctly identifies previewable files from the
  metadata written by the ingestion pipeline.
"""

import struct
import zlib
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vector_inspector.services.file_ingestion_service import FileIngestionService
from vector_inspector.utils.file_preview_utils import find_preview_paths

# ──────────────────────────────────────────────────────────────────────────────
# Shared fixtures
# ──────────────────────────────────────────────────────────────────────────────


def _png_bytes() -> bytes:
    """Minimal valid 10×10 RGB PNG."""
    sig = b"\x89PNG\r\n\x1a\n"

    def chunk(name, data):
        c = struct.pack(">I", len(data)) + name + data
        return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 10, 10, 8, 2, 0, 0, 0))
    # 10 rows × (1 filter byte + 10 × 3 RGB bytes)
    raw_row = b"\x00" + b"\xff\x00\x00" * 10
    raw = raw_row * 10
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")
    return sig + ihdr + idat + iend


@pytest.fixture()
def sample_image(tmp_path):
    """A minimal 10×10 PNG on disk."""
    path = tmp_path / "photo.png"
    path.write_bytes(_png_bytes())
    return str(path)


@pytest.fixture()
def sample_document(tmp_path):
    """A plain-text document with two paragraphs."""
    path = tmp_path / "notes.txt"
    path.write_text(
        "First paragraph about dogs.\n\nSecond paragraph about cats.",
        encoding="utf-8",
    )
    return str(path)


def _mock_connection():
    """A mock connection that records add_items calls."""
    conn = MagicMock()
    conn.get_items.return_value = {"ids": [], "metadatas": []}
    conn.get_all_items.return_value = {"ids": [], "metadatas": []}
    conn.add_items.return_value = True
    return conn


def _fake_clip():
    """CLIP model + processor returning a real 512-dim tensor."""
    import torch

    model = MagicMock()
    processor = MagicMock()
    processor.return_value = {}
    model.get_image_features.return_value = torch.ones(1, 512)
    return model, processor


def _fake_pillow(image_size=(10, 10)):
    """Pillow stub that returns a fake image of the given size."""
    fake_pillow = MagicMock()
    fake_img = MagicMock()
    fake_img.size = image_size
    fake_img.convert.return_value = fake_img
    fake_img.__array__ = MagicMock(return_value=np.zeros((*image_size, 3), dtype=np.uint8))
    fake_pillow.open.return_value = fake_img
    return fake_pillow


def _fake_sentence_transformer(dim: int = 384):
    model = MagicMock()
    model.encode.side_effect = lambda _text: np.array([0.1] * dim, dtype=np.float32)
    return model


# ──────────────────────────────────────────────────────────────────────────────
# Tests
# ──────────────────────────────────────────────────────────────────────────────


class TestMultimodalIngestion:
    """Both image and document pipelines write to the same mock collection."""

    def _ingest_image(self, connection, path):
        import torch

        clip_model, processor = _fake_clip()
        pillow = _fake_pillow()
        with (
            patch(
                "vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(clip_model, processor)
            ),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=pillow),
            patch.object(
                torch,
                "no_grad",
                return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None),
            ),
        ):
            return FileIngestionService().ingest_files(
                file_paths=[path],
                connection=connection,
                collection_name="multimodal",
                file_kind="image",
            )

    def _ingest_document(self, connection, path):
        st_model = _fake_sentence_transformer(dim=384)
        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=st_model):
            return FileIngestionService().ingest_files(
                file_paths=[path],
                connection=connection,
                collection_name="multimodal",
                file_kind="document",
                max_chunk_size=1000,
            )

    def test_image_ingestion_succeeds(self, sample_image):
        conn = _mock_connection()
        result = self._ingest_image(conn, sample_image)

        assert result.succeeded == 1
        assert result.failed == 0
        assert result.chunks_written == 1

    def test_document_ingestion_succeeds(self, sample_document):
        conn = _mock_connection()
        result = self._ingest_document(conn, sample_document)

        assert result.succeeded == 1
        assert result.failed == 0
        assert result.chunks_written == 2  # two paragraphs

    def test_sequential_image_then_document(self, sample_image, sample_document):
        """Both pipeline runs succeed independently against the same connection."""
        conn = _mock_connection()

        img_result = self._ingest_image(conn, sample_image)
        doc_result = self._ingest_document(conn, sample_document)

        assert img_result.succeeded == 1
        assert doc_result.succeeded == 1
        # 1 call for the image flush + 1 call for the document batch (both
        # chunks are flushed together in a single add_items call)
        assert conn.add_items.call_count == 2

    def test_image_embedding_is_512_dim(self, sample_image):
        conn = _mock_connection()
        self._ingest_image(conn, sample_image)

        call_kwargs = conn.add_items.call_args[1]
        embedding = call_kwargs["embeddings"][0]
        assert len(embedding) == 512

    def test_document_embedding_is_384_dim(self, sample_document):
        conn = _mock_connection()
        self._ingest_document(conn, sample_document)

        # Check the first add_items call (first chunk)
        first_call_kwargs = conn.add_items.call_args_list[0][1]
        embedding = first_call_kwargs["embeddings"][0]
        assert len(embedding) == 384

    def test_image_metadata_contains_file_path(self, sample_image):
        conn = _mock_connection()
        self._ingest_image(conn, sample_image)

        call_kwargs = conn.add_items.call_args[1]
        metadata = call_kwargs["metadatas"][0]
        assert "file_path" in metadata
        assert metadata["file_path"] == sample_image

    def test_document_metadata_contains_file_path(self, sample_document):
        conn = _mock_connection()
        self._ingest_document(conn, sample_document)

        first_call_kwargs = conn.add_items.call_args_list[0][1]
        metadata = first_call_kwargs["metadatas"][0]
        assert "file_path" in metadata
        assert metadata["file_path"] == sample_document

    def test_document_metadata_contains_chunk_fields(self, sample_document):
        conn = _mock_connection()
        self._ingest_document(conn, sample_document)

        first_call_kwargs = conn.add_items.call_args_list[0][1]
        metadata = first_call_kwargs["metadatas"][0]
        assert "chunk_index" in metadata
        assert "chunk_total" in metadata
        assert "parent_id" in metadata


# ──────────────────────────────────────────────────────────────────────────────
# Preview path detection on ingested metadata
# ──────────────────────────────────────────────────────────────────────────────


class TestPreviewPathsFromIngestedMetadata:
    """find_preview_paths() should correctly identify previewable files from
    metadata as it is written by both ingestion pipelines."""

    def test_image_metadata_is_previewable(self, sample_image):
        """Image metadata with file_path pointing to a .png is previewable."""
        metadata = {"file_path": sample_image, "file_name": "photo.png"}
        paths = find_preview_paths(metadata)
        assert paths == [sample_image]

    def test_document_metadata_is_previewable(self, sample_document):
        """Document metadata with file_path pointing to a .txt is previewable."""
        metadata = {
            "file_path": sample_document,
            "file_name": "notes.txt",
            "chunk_index": 0,
            "chunk_total": 2,
        }
        paths = find_preview_paths(metadata)
        assert paths == [sample_document]

    def test_missing_file_not_returned(self, tmp_path):
        """Metadata referencing a deleted file must not produce a preview path."""
        metadata = {"file_path": str(tmp_path / "gone.png")}
        paths = find_preview_paths(metadata)
        assert paths == []

    def test_image_and_document_both_previewable(self, sample_image, sample_document):
        """When a metadata row has both file types, both paths are returned."""
        metadata = {
            "image_path": sample_image,
            "doc_path": sample_document,
        }
        paths = find_preview_paths(metadata)
        assert sample_image in paths
        assert sample_document in paths
