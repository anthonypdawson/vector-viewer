"""Tests for FileIngestionService — image and document pipelines."""

import os
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from vector_inspector.services.file_ingestion_service import (
    FileIngestionService,
    IngestionResult,
    _chunk_text,
    _count_existing_chunks,
    _delete_chunks_by_parent,
    _extract_text,
    _get_stored_chunk_total,
    _is_document_file,
    _is_image_file,
    _l2_normalize,
    _scan_folder,
)

# ---------------------------------------------------------------------------
# Unit helpers
# ---------------------------------------------------------------------------


class TestL2Normalize:
    def test_unit_vector_unchanged(self):
        v = [1.0, 0.0, 0.0]
        out = _l2_normalize(v)
        assert abs(out[0] - 1.0) < 1e-6

    def test_normalizes_vector(self):
        v = [3.0, 4.0]
        out = _l2_normalize(v)
        norm = sum(x**2 for x in out) ** 0.5
        assert abs(norm - 1.0) < 1e-6

    def test_zero_vector_returns_original(self):
        v = [0.0, 0.0, 0.0]
        assert _l2_normalize(v) == v


class TestChunkText:
    def test_short_text_returns_single_chunk(self):
        result = _chunk_text("hello world", 1000)
        assert result == ["hello world"]

    def test_paragraph_split(self):
        text = "para one\n\npara two\n\npara three"
        result = _chunk_text(text, 1000)
        assert len(result) == 3

    def test_hard_split_long_paragraph(self):
        para = "x" * 500
        result = _chunk_text(para, 100)
        assert len(result) == 5
        for chunk in result:
            assert len(chunk) <= 100

    def test_empty_paragraphs_skipped(self):
        result = _chunk_text("a\n\n\n\nb", 1000)
        assert result == ["a", "b"]

    def test_whitespace_only_text_returns_placeholder(self):
        result = _chunk_text("   \n\n   ", 1000)
        assert result == [""]


class TestFileTypeHelpers:
    def test_is_image_file(self, tmp_path):
        f = tmp_path / "img.png"
        f.write_bytes(b"")
        assert _is_image_file(str(f))

    def test_is_not_image_file(self, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("hello")
        assert not _is_image_file(str(f))

    def test_is_document_pdf(self, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")
        assert _is_document_file(str(f))

    def test_is_document_docx(self, tmp_path):
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04")  # ZIP magic
        assert _is_document_file(str(f))

    def test_is_document_plain_text(self, tmp_path):
        f = tmp_path / "script.py"
        f.write_text("print('hello')")
        assert _is_document_file(str(f))

    def test_image_not_document(self, tmp_path):
        f = tmp_path / "img.jpg"
        f.write_bytes(b"\xff\xd8\xff")
        assert not _is_document_file(str(f))


class TestScanFolder:
    def test_scan_folder_images(self, tmp_path):
        (tmp_path / "a.png").write_bytes(b"")
        (tmp_path / "b.jpg").write_bytes(b"")
        (tmp_path / "readme.txt").write_text("text")
        paths = _scan_folder(str(tmp_path), "image", recursive=False)
        basenames = [os.path.basename(p) for p in paths]
        assert "a.png" in basenames
        assert "b.jpg" in basenames
        assert "readme.txt" not in basenames

    def test_scan_folder_recursive(self, tmp_path):
        sub = tmp_path / "sub"
        sub.mkdir()
        (sub / "deep.png").write_bytes(b"")
        (tmp_path / "top.png").write_bytes(b"")

        non_recursive = _scan_folder(str(tmp_path), "image", recursive=False)
        recursive = _scan_folder(str(tmp_path), "image", recursive=True)
        assert len(non_recursive) == 1
        assert len(recursive) == 2

    def test_scan_folder_documents(self, tmp_path):
        (tmp_path / "doc.txt").write_text("text")
        (tmp_path / "img.png").write_bytes(b"")
        paths = _scan_folder(str(tmp_path), "document", recursive=False)
        basenames = [os.path.basename(p) for p in paths]
        assert "doc.txt" in basenames
        assert "img.png" not in basenames


class TestCountExistingChunks:
    def test_returns_count(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": ["id-0", "id-1"]}
        assert _count_existing_chunks(conn, "coll", "abc123") == 2

    def test_returns_zero_on_error(self):
        conn = MagicMock()
        conn.get_all_items.side_effect = Exception("not found")
        assert _count_existing_chunks(conn, "coll", "abc123") == 0


class TestIngestionResult:
    def test_summary_no_files(self):
        r = IngestionResult()
        assert "No files" in r.summary()

    def test_summary_with_results(self):
        r = IngestionResult(total=3, succeeded=2, skipped=1, chunks_written=5)
        s = r.summary()
        assert "2 file" in s
        assert "5 chunk" in s
        assert "1 skipped" in s

    def test_summary_with_failures(self):
        r = IngestionResult(total=2, succeeded=1, failed=1, chunks_written=2)
        s = r.summary()
        assert "1 failed" in s


# ---------------------------------------------------------------------------
# Image ingestion pipeline (CLIP mocked)
# ---------------------------------------------------------------------------


def _make_connection(existing_ids=None):
    """Build a minimal mock connection."""
    conn = MagicMock()
    existing_ids = existing_ids or []
    conn.get_items.return_value = {"ids": existing_ids, "metadatas": []}
    conn.get_all_items.return_value = {"ids": existing_ids, "metadatas": []}
    conn.add_items.return_value = True
    return conn


def _fake_clip_outputs():
    """Return fake model + processor that output a 512-dim embedding."""
    import torch

    model = MagicMock()
    processor = MagicMock()
    # Use a real tensor so isinstance(features, torch.Tensor) is True and the
    # unwrap guard in _ingest_image_files passes correctly.
    fake_features = torch.ones(1, 512)
    model.get_image_features.return_value = fake_features
    processor.return_value = {}
    return model, processor


@pytest.fixture()
def sample_png(tmp_path):
    """Write a minimal 1x1 PNG file and return its path."""
    import struct
    import zlib

    def _png_bytes() -> bytes:
        sig = b"\x89PNG\r\n\x1a\n"

        def chunk(name, data):
            c = struct.pack(">I", len(data)) + name + data
            return c + struct.pack(">I", zlib.crc32(name + data) & 0xFFFFFFFF)

        ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        raw = b"\x00\xff\x00\x00"  # filter byte + 1 RGB pixel
        idat = chunk(b"IDAT", zlib.compress(raw))
        iend = chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    path = tmp_path / "test.png"
    path.write_bytes(_png_bytes())
    return str(path)


class TestImageIngestion:
    def test_ingest_single_image(self, sample_png):
        conn = _make_connection()
        model, processor = _fake_clip_outputs()

        fake_pillow = MagicMock()
        fake_img = MagicMock()
        fake_img.size = (10, 10)
        fake_img.convert.return_value = fake_img
        fake_img.__array__ = MagicMock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
        fake_pillow.open.return_value = fake_img

        import torch

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
            patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=[sample_png],
                connection=conn,
                collection_name="images",
                file_kind="image",
            )

        assert result.total == 1
        assert result.succeeded == 1
        assert result.failed == 0
        assert result.chunks_written == 1
        conn.add_items.assert_called_once()
        call_kwargs = conn.add_items.call_args[1]
        assert len(call_kwargs["ids"]) == 1
        assert len(call_kwargs["embeddings"][0]) == 512

    def test_skips_duplicate_image(self, sample_png):
        # Return existing id so duplicate check fires
        conn = MagicMock()
        conn.get_items.return_value = {"ids": ["some-hash"], "metadatas": [{}]}
        model, processor = _fake_clip_outputs()
        fake_pillow = MagicMock()

        import torch

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
            patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=[sample_png],
                connection=conn,
                collection_name="images",
                file_kind="image",
                overwrite=False,
            )

        assert result.skipped == 1
        assert result.succeeded == 0
        conn.add_items.assert_not_called()

    def test_nonexistent_file_counts_as_failure(self):
        conn = _make_connection()
        model, processor = _fake_clip_outputs()
        fake_pillow = MagicMock()

        import torch

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
            patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=["/does/not/exist.png"],
                connection=conn,
                collection_name="images",
                file_kind="image",
            )

        assert result.failed == 1
        assert result.succeeded == 0


# ---------------------------------------------------------------------------
# Document ingestion pipeline (SentenceTransformer mocked)
# ---------------------------------------------------------------------------


def _fake_sentence_transformer():
    model = MagicMock()
    model.encode.side_effect = lambda _text: np.array([0.1] * 384, dtype=np.float32)
    return model


class TestDocumentIngestion:
    def test_ingest_plain_text(self, tmp_path):
        doc = tmp_path / "note.txt"
        doc.write_text("Hello world.\n\nSecond paragraph here.", encoding="utf-8")

        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
                max_chunk_size=1000,
            )

        assert result.succeeded == 1
        assert result.failed == 0
        assert result.chunks_written == 2  # two paragraphs → two chunks
        conn.add_items.assert_called()
        # Each chunk id ends with -0 or -1
        all_ids = conn.add_items.call_args[1]["ids"]
        assert any(i.endswith("-0") for i in all_ids)

    def test_chunk_ids_use_hash_prefix(self, tmp_path):
        doc = tmp_path / "chunk.txt"
        doc.write_text("paragraph one\n\nparagraph two", encoding="utf-8")

        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
            )

        ids = conn.add_items.call_args[1]["ids"]
        # Both ids must share the same hash prefix
        prefixes = {i.rsplit("-", 1)[0] for i in ids}
        assert len(prefixes) == 1
        assert result.chunks_written == 2

    def test_skip_fully_ingested_document(self, tmp_path):
        doc = tmp_path / "known.txt"
        doc.write_text("alpha\n\nbeta", encoding="utf-8")

        conn = MagicMock()
        # Both chunks already present and chunk_total stored
        conn.get_all_items.return_value = {
            "ids": ["hash-0", "hash-1"],
            "metadatas": [{"chunk_total": 2, "parent_id": "x"}],
        }
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
                overwrite=False,
            )

        assert result.skipped == 1
        conn.add_items.assert_not_called()

    def test_overwrite_deletes_existing_chunks(self, tmp_path):
        doc = tmp_path / "rewrite.txt"
        doc.write_text("existing content", encoding="utf-8")

        conn = MagicMock()
        # Simulate one existing chunk
        conn.get_all_items.return_value = {"ids": ["hash-0"], "metadatas": [{"chunk_total": 1, "parent_id": "x"}]}
        conn.delete_items.return_value = None
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
                overwrite=True,
            )

        conn.delete_items.assert_called()
        assert result.succeeded == 1

    def test_partial_ingestion_triggers_cleanup_and_reingest(self, tmp_path):
        doc = tmp_path / "partial.txt"
        doc.write_text("para a\n\npara b\n\npara c", encoding="utf-8")

        conn = MagicMock()
        # Only 1 of 3 chunks present (partial)
        conn.get_all_items.return_value = {"ids": ["hash-0"], "metadatas": [{"chunk_total": 3, "parent_id": "x"}]}
        conn.delete_items.return_value = None
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
                overwrite=False,
            )

        conn.delete_items.assert_called()
        assert result.succeeded == 1
        assert result.chunks_written == 3

    def test_empty_text_file_counts_as_failure(self, tmp_path):
        doc = tmp_path / "empty.txt"
        doc.write_text("", encoding="utf-8")

        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
            )

        assert result.failed == 1

    def test_nonexistent_document_counts_as_failure(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            result = FileIngestionService().ingest_files(
                file_paths=["/does/not/exist.txt"],
                connection=conn,
                collection_name="docs",
                file_kind="document",
            )

        assert result.failed == 1

    def test_chunk_total_in_metadata(self, tmp_path):
        """chunk_total must be written correctly on every chunk's metadata."""
        doc = tmp_path / "chunks.txt"
        doc.write_text("a\n\nb\n\nc", encoding="utf-8")

        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
            )

        metadatas = conn.add_items.call_args[1]["metadatas"]
        for meta in metadatas:
            assert meta["chunk_total"] == 3
            assert "chunk_index" in meta

    def test_progress_callback_called(self, tmp_path):
        doc = tmp_path / "progress.txt"
        doc.write_text("one paragraph", encoding="utf-8")

        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        model = _fake_sentence_transformer()
        calls = []

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model):
            FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
                progress_callback=lambda done, total, filename: calls.append((done, total, filename)),
            )

        assert len(calls) >= 2  # at least start + end


# ---------------------------------------------------------------------------
# Folder ingestion
# ---------------------------------------------------------------------------


class TestFolderIngestion:
    def test_ingest_folder_images(self, tmp_path):
        (tmp_path / "a.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
        (tmp_path / "b.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)
        (tmp_path / "notes.txt").write_text("ignore me")

        conn = _make_connection()
        model, processor = _fake_clip_outputs()
        fake_pillow = MagicMock()
        fake_img = MagicMock()
        fake_img.size = (10, 10)
        fake_img.convert.return_value = fake_img
        fake_img.__array__ = MagicMock(return_value=np.zeros((10, 10, 3), dtype=np.uint8))
        fake_pillow.open.return_value = fake_img

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
        ):
            import torch

            with patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ):
                result = FileIngestionService().ingest_folder(
                    folder_path=str(tmp_path),
                    connection=conn,
                    collection_name="images",
                    file_kind="image",
                )

        assert result.total == 2
        assert result.succeeded == 2


# ---------------------------------------------------------------------------
# _extract_text
# ---------------------------------------------------------------------------


class TestExtractText:
    def test_plain_text(self, tmp_path):
        f = tmp_path / "readme.txt"
        f.write_text("Hello world\nLine 2")
        text, page_count = _extract_text(str(f))
        assert "Hello world" in text
        assert page_count is None

    def test_html_strips_tags(self, tmp_path):
        f = tmp_path / "page.html"
        f.write_text("<html><body><p>Hello</p></body></html>")
        text, page_count = _extract_text(str(f))
        assert "<p>" not in text
        assert "Hello" in text
        assert page_count is None

    def test_xml_strips_tags(self, tmp_path):
        f = tmp_path / "data.xml"
        f.write_text("<root><item>Value</item></root>")
        text, _ = _extract_text(str(f))
        assert "<item>" not in text
        assert "Value" in text

    def test_pdf_extraction(self, tmp_path):
        """PDF extraction via mocked pypdf."""
        f = tmp_path / "doc.pdf"
        f.write_bytes(b"%PDF-1.4")

        fake_page = MagicMock()
        fake_page.extract_text.return_value = "Page 1 text"
        fake_reader = MagicMock()
        fake_reader.pages = [fake_page]

        fake_pypdf = MagicMock()
        fake_pypdf.PdfReader.return_value = fake_reader

        with patch("vector_inspector.services.file_ingestion_service._lazy_pypdf", return_value=fake_pypdf):
            text, page_count = _extract_text(str(f))

        assert "Page 1 text" in text
        assert page_count == 1

    def test_docx_extraction(self, tmp_path):
        """Docx extraction via mocked python-docx."""
        f = tmp_path / "doc.docx"
        f.write_bytes(b"PK\x03\x04")

        para1 = MagicMock()
        para1.text = "First paragraph"
        para2 = MagicMock()
        para2.text = "Second paragraph"
        fake_doc = MagicMock()
        fake_doc.paragraphs = [para1, para2]

        fake_docx = MagicMock()
        fake_docx.Document.return_value = fake_doc

        with patch("vector_inspector.services.file_ingestion_service._lazy_docx", return_value=fake_docx):
            text, page_count = _extract_text(str(f))

        assert "First paragraph" in text
        assert "Second paragraph" in text
        assert page_count is None


# ---------------------------------------------------------------------------
# _get_stored_chunk_total / _delete_chunks_by_parent
# ---------------------------------------------------------------------------


class TestChunkHelpers:
    def test_get_stored_chunk_total_returns_value(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"metadatas": [{"chunk_total": 5}]}
        assert _get_stored_chunk_total(conn, "coll", "hash123") == 5

    def test_get_stored_chunk_total_returns_none_on_empty(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"metadatas": []}
        assert _get_stored_chunk_total(conn, "coll", "hash123") is None

    def test_get_stored_chunk_total_returns_none_on_error(self):
        conn = MagicMock()
        conn.get_all_items.side_effect = Exception("err")
        assert _get_stored_chunk_total(conn, "coll", "hash123") is None

    def test_delete_chunks_by_parent(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": ["h-0", "h-1"]}
        _delete_chunks_by_parent(conn, "coll", "hash123")
        conn.delete_items.assert_called_once_with(collection_name="coll", ids=["h-0", "h-1"])

    def test_delete_chunks_by_parent_no_ids(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": []}
        _delete_chunks_by_parent(conn, "coll", "hash123")
        conn.delete_items.assert_not_called()

    def test_delete_chunks_by_parent_error_does_not_raise(self):
        conn = MagicMock()
        conn.get_all_items.side_effect = Exception("boom")
        _delete_chunks_by_parent(conn, "coll", "hash123")  # Should not raise


# ---------------------------------------------------------------------------
# Image: minimum dimension rejection
# ---------------------------------------------------------------------------


class TestMinImageDimension:
    def test_tiny_image_rejected(self, tmp_path):
        """Images below 3×3 are rejected as too small."""
        img_file = tmp_path / "tiny.png"
        img_file.write_bytes(b"\x89PNG" + b"\x00" * 10)

        conn = _make_connection()
        model, processor = _fake_clip_outputs()
        fake_pillow = MagicMock()
        fake_img = MagicMock()
        fake_img.size = (2, 2)  # Below _MIN_IMAGE_DIM=3
        fake_img.convert.return_value = fake_img
        fake_pillow.open.return_value = fake_img

        import torch

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
            patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=[str(img_file)],
                connection=conn,
                collection_name="images",
                file_kind="image",
            )

        assert result.failed == 1
        assert result.succeeded == 0
        assert any("too small" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Image: _flush failure path
# ---------------------------------------------------------------------------


class TestImageFlushFailure:
    def test_flush_failure_raises(self, tmp_path):
        """When add_items returns False at final flush, RuntimeError propagates."""
        img_file = tmp_path / "photo.jpg"
        img_file.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 10)

        conn = _make_connection()
        conn.add_items.return_value = False  # flush fails

        model, processor = _fake_clip_outputs()
        fake_pillow = MagicMock()
        fake_img = MagicMock()
        fake_img.size = (100, 100)
        fake_img.convert.return_value = fake_img
        fake_img.__array__ = MagicMock(return_value=np.zeros((100, 100, 3), dtype=np.uint8))
        fake_pillow.open.return_value = fake_img

        import torch

        with (
            patch("vector_inspector.utils.lazy_imports.get_clip_model_and_processor", return_value=(model, processor)),
            patch("vector_inspector.utils.lazy_imports.get_pillow", return_value=fake_pillow),
            patch.object(
                torch, "no_grad", return_value=MagicMock(__enter__=lambda _s: _s, __exit__=lambda _s, *_a: None)
            ),
            pytest.raises(RuntimeError, match="Failed to write"),
        ):
            FileIngestionService().ingest_files(
                file_paths=[str(img_file)],
                connection=conn,
                collection_name="images",
                file_kind="image",
            )


# ---------------------------------------------------------------------------
# Document: flush failure at final flush
# ---------------------------------------------------------------------------


class TestDocumentFlushFailure:
    def test_final_flush_failure_recorded(self, tmp_path):
        """When add_items returns False at final flush, the document is recorded as failed."""
        doc_file = tmp_path / "test.txt"
        doc_file.write_text("Hello world test content for embedding purposes.")

        conn = _make_connection()
        conn.add_items.return_value = False  # flush fails

        fake_model = MagicMock()
        fake_model.encode.return_value = MagicMock(tolist=lambda: [0.1] * 384)

        with patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=fake_model):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc_file)],
                connection=conn,
                collection_name="docs",
                file_kind="document",
            )

        assert result.failed == 1
        assert result.succeeded == 0
        assert any("failed" in e.lower() for e in result.errors)


# ---------------------------------------------------------------------------
# Telemetry events
# ---------------------------------------------------------------------------


class TestIngestionTelemetry:
    """ingest_files fires ingestion.started and ingestion.completed telemetry events."""

    def _doc_conn(self):
        conn = MagicMock()
        conn.get_all_items.return_value = {"ids": [], "metadatas": []}
        conn.add_items.return_value = True
        return conn

    def test_telemetry_start_and_end_fired_for_documents(self, tmp_path):
        doc = tmp_path / "a.txt"
        doc.write_text("hello world content for ingestion telemetry test")

        conn = self._doc_conn()
        model = _fake_sentence_transformer()
        events: list[tuple] = []

        with (
            patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model),
            patch(
                "vector_inspector.services.file_ingestion_service.TelemetryService.send_event",
                side_effect=lambda name, payload: events.append((name, payload)),
            ),
        ):
            FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="test_col",
                file_kind="document",
            )

        names = [e[0] for e in events]
        assert "ingestion.started" in names
        assert "ingestion.completed" in names

        start_meta = next(e[1]["metadata"] for e in events if e[0] == "ingestion.started")
        assert start_meta["file_kind"] == "document"
        assert start_meta["file_count"] == 1
        assert start_meta["collection_name"] == "test_col"

        end_meta = next(e[1]["metadata"] for e in events if e[0] == "ingestion.completed")
        assert end_meta["succeeded"] == 1
        assert "duration_ms" in end_meta

    def test_telemetry_completed_reflects_stats(self, tmp_path):
        doc = tmp_path / "b.txt"
        doc.write_text("paragraph one\n\nparagraph two")

        conn = self._doc_conn()
        model = _fake_sentence_transformer()
        events: list[tuple] = []

        with (
            patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model),
            patch(
                "vector_inspector.services.file_ingestion_service.TelemetryService.send_event",
                side_effect=lambda name, payload: events.append((name, payload)),
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="col",
                file_kind="document",
            )

        end_meta = next(e[1]["metadata"] for e in events if e[0] == "ingestion.completed")
        assert end_meta["total"] == result.total
        assert end_meta["succeeded"] == result.succeeded
        assert end_meta["chunks_written"] == result.chunks_written

    def test_telemetry_exception_does_not_propagate(self, tmp_path):
        """A broken TelemetryService must not abort ingestion."""
        doc = tmp_path / "c.txt"
        doc.write_text("some text to ingest safely")

        conn = self._doc_conn()
        model = _fake_sentence_transformer()

        with (
            patch("vector_inspector.utils.lazy_imports.get_sentence_transformer", return_value=model),
            patch(
                "vector_inspector.services.file_ingestion_service.TelemetryService.send_event",
                side_effect=RuntimeError("telemetry down"),
            ),
        ):
            result = FileIngestionService().ingest_files(
                file_paths=[str(doc)],
                connection=conn,
                collection_name="col",
                file_kind="document",
            )

        assert result.succeeded == 1
