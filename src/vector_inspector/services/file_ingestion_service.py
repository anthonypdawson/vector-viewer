"""File ingestion service — image and document pipelines."""

import hashlib
import os
import pathlib
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

import numpy as np

from vector_inspector.core.logging import log_error, log_info
from vector_inspector.services.telemetry_service import TelemetryService
from vector_inspector.utils.file_preview_utils import IMAGE_EXTENSIONS, is_text_file


@dataclass
class IngestionResult:
    """Result of an ingestion run.

    total, succeeded, skipped, and failed always count **source files**, not chunks.
    chunks_written is the total number of chunk items actually upserted.
    """

    total: int = 0
    succeeded: int = 0
    skipped: int = 0  # files where all chunks already present (hash match)
    failed: int = 0  # files where extraction or embedding raised an error
    errors: list[str] = field(default_factory=list)
    chunks_written: int = 0  # total individual chunk items upserted across all files

    def summary(self) -> str:
        """Return a human-readable one-line summary suitable for a QMessageBox."""
        if self.total == 0:
            return "No files found to ingest."
        parts = [f"Ingested {self.succeeded} file(s) ({self.chunks_written} chunk(s))"]
        if self.skipped:
            parts.append(f"{self.skipped} skipped (duplicate)")
        if self.failed:
            parts.append(f"{self.failed} failed")
        return ". ".join(parts) + "."


# ---------------------------------------------------------------------------
# Document text extraction
# ---------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")


def _extract_text(path: str) -> tuple[str, int | None]:
    """Extract readable text from a document path.

    Returns (text, page_count).  page_count is None for non-PDF files.
    Raises OSError or ImportError on failure.
    """
    suffix = pathlib.Path(path).suffix.lower()

    if suffix == ".pdf":
        pypdf = _lazy_pypdf()
        reader = pypdf.PdfReader(path)
        pages = [page.extract_text() or "" for page in reader.pages]
        return "\n\n".join(pages), len(pages)

    if suffix == ".docx":
        docx = _lazy_docx()
        doc = docx.Document(path)
        return "\n\n".join(para.text for para in doc.paragraphs if para.text), None

    if suffix in {".html", ".xml"}:
        with open(path, encoding="utf-8", errors="replace") as fh:
            raw = fh.read()
        return _TAG_RE.sub(" ", raw), None

    # Plain text / source file — rely on UTF-8 with replacement
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read(), None


def _lazy_pypdf() -> Any:
    from vector_inspector.utils.lazy_imports import get_pypdf

    return get_pypdf()


def _lazy_docx() -> Any:
    from vector_inspector.utils.lazy_imports import get_python_docx

    return get_python_docx()


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------


def _chunk_text(text: str, max_chunk_size: int) -> list[str]:
    """Split *text* into chunks of at most *max_chunk_size* characters.

    Strategy:
    1. Split on double newlines (paragraph boundaries).
    2. Hard-split any paragraph that still exceeds max_chunk_size.
    """
    paragraphs = text.split("\n\n")
    chunks: list[str] = []
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= max_chunk_size:
            chunks.append(para)
        else:
            # Hard split
            for start in range(0, len(para), max_chunk_size):
                chunks.append(para[start : start + max_chunk_size])
    return chunks if chunks else [""]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _md5(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(65536), b""):
            h.update(block)
    return h.hexdigest()


# Minimum pixel dimension CLIP can process reliably.  Images smaller than
# this in either axis cause ambiguous-channel errors in the image processor.
_MIN_IMAGE_DIM = 3


def _l2_normalize(vec: list[float]) -> list[float]:
    arr = np.array(vec, dtype=np.float32).flatten()
    norm = np.linalg.norm(arr)
    if norm == 0.0:
        return arr.tolist()
    return (arr / norm).tolist()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _is_image_file(path: str) -> bool:
    return pathlib.Path(path).suffix.lower() in IMAGE_EXTENSIONS


def _is_document_file(path: str) -> bool:
    suffix = pathlib.Path(path).suffix.lower()
    if suffix in {".pdf", ".docx"}:
        return True
    return is_text_file(path) and suffix not in IMAGE_EXTENSIONS


def _scan_folder(
    folder_path: str,
    file_kind: Literal["image", "document"],
    recursive: bool,
) -> list[str]:
    """Collect file paths under *folder_path* matching *file_kind*."""
    matched: list[str] = []
    walk_fn = os.walk if recursive else _shallow_walk
    for root, _dirs, files in walk_fn(folder_path):
        for fname in sorted(files):
            full = os.path.join(root, fname)
            if (file_kind == "image" and _is_image_file(full)) or (file_kind == "document" and _is_document_file(full)):
                matched.append(full)
    return matched


def _shallow_walk(folder_path: str):
    """Single-level os.walk replacement."""
    with os.scandir(folder_path) as entries:
        files = [e.name for e in entries if e.is_file()]
    yield folder_path, [], files


def _count_existing_chunks(connection: Any, collection_name: str, parent_id: str) -> int:
    """Query how many chunk items with parent_id already exist in the collection."""
    try:
        results = connection.get_all_items(
            collection_name,
            where={"parent_id": parent_id},
            limit=10000,
        )
        ids = (results or {}).get("ids", [])
        return len(ids)
    except Exception:
        return 0


def _get_stored_chunk_total(connection: Any, collection_name: str, parent_id: str) -> int | None:
    """Return the chunk_total value stored on existing chunks, or None if unavailable."""
    try:
        results = connection.get_all_items(
            collection_name,
            where={"parent_id": parent_id},
            limit=1,
        )
        metadatas = (results or {}).get("metadatas") or []
        if metadatas and metadatas[0]:
            return metadatas[0].get("chunk_total")
    except Exception:
        pass
    return None


def _delete_chunks_by_parent(connection: Any, collection_name: str, parent_id: str) -> None:
    """Best-effort deletion of all chunks belonging to *parent_id*."""
    try:
        results = connection.get_all_items(
            collection_name,
            where={"parent_id": parent_id},
            limit=10000,
        )
        ids = (results or {}).get("ids", [])
        if ids:
            connection.delete_items(collection_name=collection_name, ids=ids)
    except Exception as exc:
        log_error("Best-effort chunk cleanup failed for parent_id=%s: %s", parent_id, exc)


# ---------------------------------------------------------------------------
# Main service
# ---------------------------------------------------------------------------


class FileIngestionService:
    """Unified ingestion service for images and documents."""

    def ingest_folder(
        self,
        folder_path: str,
        connection: Any,
        collection_name: str,
        file_kind: Literal["image", "document"],
        batch_size: int = 16,
        recursive: bool = False,
        overwrite: bool = False,
        max_chunk_size: int = 1000,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> IngestionResult:
        """Scan *folder_path* for files matching *file_kind* and ingest them."""
        file_paths = _scan_folder(folder_path, file_kind, recursive)
        return self.ingest_files(
            file_paths=file_paths,
            connection=connection,
            collection_name=collection_name,
            file_kind=file_kind,
            batch_size=batch_size,
            overwrite=overwrite,
            max_chunk_size=max_chunk_size,
            source_folder=folder_path,
            progress_callback=progress_callback,
        )

    def ingest_files(
        self,
        file_paths: list[str],
        connection: Any,
        collection_name: str,
        file_kind: Literal["image", "document"],
        batch_size: int = 16,
        overwrite: bool = False,
        max_chunk_size: int = 1000,
        source_folder: str | None = None,
        progress_callback: Callable[[int, int, str], None] | None = None,
    ) -> IngestionResult:
        """Ingest an explicit list of files."""
        import time as _time

        result = IngestionResult(total=len(file_paths))

        log_info(
            "Ingestion started — kind=%s collection=%s files=%d overwrite=%s",
            file_kind,
            collection_name,
            len(file_paths),
            overwrite,
        )
        try:
            TelemetryService.send_event(
                "ingestion.started",
                {
                    "metadata": {
                        "file_kind": file_kind,
                        "collection_name": collection_name,
                        "file_count": len(file_paths),
                        "overwrite": overwrite,
                        "folder_mode": source_folder is not None,
                    }
                },
            )
        except Exception:
            pass

        _start = _time.monotonic()

        if file_kind == "image":
            self._ingest_image_files(
                file_paths,
                connection,
                collection_name,
                batch_size,
                overwrite,
                source_folder,
                result,
                progress_callback,
            )
        else:
            self._ingest_document_files(
                file_paths,
                connection,
                collection_name,
                batch_size,
                overwrite,
                max_chunk_size,
                source_folder,
                result,
                progress_callback,
            )

        duration_ms = int((_time.monotonic() - _start) * 1000)
        log_info(
            "Ingestion complete — kind=%s collection=%s succeeded=%d skipped=%d failed=%d chunks=%d duration_ms=%d",
            file_kind,
            collection_name,
            result.succeeded,
            result.skipped,
            result.failed,
            result.chunks_written,
            duration_ms,
        )
        try:
            TelemetryService.send_event(
                "ingestion.completed",
                {
                    "metadata": {
                        "file_kind": file_kind,
                        "collection_name": collection_name,
                        "total": result.total,
                        "succeeded": result.succeeded,
                        "skipped": result.skipped,
                        "failed": result.failed,
                        "chunks_written": result.chunks_written,
                        "duration_ms": duration_ms,
                    }
                },
            )
        except Exception:
            pass

        return result

    # ------------------------------------------------------------------
    # Image pipeline
    # ------------------------------------------------------------------

    def _ingest_image_files(
        self,
        file_paths: list[str],
        connection: Any,
        collection_name: str,
        batch_size: int,
        overwrite: bool,
        source_folder: str | None,
        result: IngestionResult,
        progress_callback: Callable[[int, int, str], None] | None,
    ) -> None:
        from vector_inspector.utils.lazy_imports import get_clip_model_and_processor, get_pillow

        model, processor = get_clip_model_and_processor()
        Image = get_pillow()

        import torch

        batch_ids: list[str] = []
        batch_embeddings: list[list[float]] = []
        batch_documents: list[str] = []
        batch_metadatas: list[dict[str, Any]] = []

        def _flush() -> None:
            if batch_ids:
                count = len(batch_ids)
                ok = connection.add_items(
                    collection_name=collection_name,
                    ids=batch_ids[:],
                    embeddings=batch_embeddings[:],
                    documents=batch_documents[:],
                    metadatas=batch_metadatas[:],
                )
                batch_ids.clear()
                batch_embeddings.clear()
                batch_documents.clear()
                batch_metadatas.clear()
                if not ok:
                    raise RuntimeError(
                        f"Failed to write {count} item(s) to '{collection_name}' — see error log above for details"
                    )
                result.chunks_written += count

        for idx, path in enumerate(file_paths):
            if progress_callback:
                progress_callback(idx, len(file_paths), os.path.basename(path))

            try:
                # Validate
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    result.failed += 1
                    result.errors.append(f"{path}: file not found or empty")
                    continue
                if not _is_image_file(path):
                    result.failed += 1
                    result.errors.append(f"{path}: unsupported extension")
                    continue

                file_hash = _md5(path)

                # Duplicate / overwrite check
                try:
                    existing = connection.get_items(collection_name, [file_hash])
                    has_existing = bool((existing or {}).get("ids"))
                except Exception:
                    has_existing = False

                if has_existing:
                    if not overwrite:
                        result.skipped += 1
                        continue
                    # overwrite=True: remove stale entry so add_items succeeds
                    try:
                        connection.delete_items(collection_name=collection_name, ids=[file_hash])
                    except Exception:
                        pass

                # Load image — convert to numpy array so CLIP processor always
                # receives an explicit (H, W, 3) uint8 array regardless of
                # original colour mode (L, P, RGBA, etc.).
                import numpy as np

                image = Image.open(path).convert("RGB")
                width, height = image.size

                if width < _MIN_IMAGE_DIM or height < _MIN_IMAGE_DIM:
                    result.failed += 1
                    result.errors.append(
                        f"{os.path.basename(path)}: image too small ({width}x{height}), "
                        f"minimum {_MIN_IMAGE_DIM}x{_MIN_IMAGE_DIM}"
                    )
                    continue

                image_np = np.array(image)

                # Embed
                inputs = processor(images=image_np, return_tensors="pt")
                with torch.no_grad():
                    features = model.get_image_features(**inputs)
                # Some HuggingFace CLIP variants return BaseModelOutputWithPooling
                # instead of a raw tensor.  Unwrap to the pooled tensor before
                # normalising to avoid accidentally encoding the full hidden state
                # (shape (1, 50, 768) → 38400 when flattened).
                if not isinstance(features, torch.Tensor):
                    if hasattr(features, "pooler_output") and features.pooler_output is not None:
                        features = features.pooler_output
                    elif hasattr(features, "last_hidden_state"):
                        features = features.last_hidden_state[:, 0]
                    else:
                        raise TypeError(
                            f"CLIP get_image_features returned unexpected type "
                            f"{type(features).__name__}; expected a Tensor or "
                            "BaseModelOutputWithPooling"
                        )
                embedding = _l2_normalize(features[0].tolist())

                filename = os.path.basename(path)
                meta: dict[str, Any] = {
                    "file_path": os.path.abspath(path),
                    "filename": filename,
                    "file_hash": file_hash,
                    "format": pathlib.Path(path).suffix.lstrip(".").lower(),
                    "file_type": "image",
                    "ingested_at": _utc_now(),
                    "width": width,
                    "height": height,
                }
                if source_folder:
                    meta["source_folder"] = os.path.abspath(source_folder)

                batch_ids.append(file_hash)
                batch_embeddings.append(embedding)
                batch_documents.append(filename)
                batch_metadatas.append(meta)

                if len(batch_ids) >= batch_size:
                    _flush()

                result.succeeded += 1
                log_info("Ingested image: %s", filename)

            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{os.path.basename(path)}: {str(exc)[:300]}")
                log_error("Image ingestion failed for %s: %.300s", path, str(exc), exc_info=True)

        _flush()

        if progress_callback:
            progress_callback(len(file_paths), len(file_paths), "")

    # ------------------------------------------------------------------
    # Document pipeline
    # ------------------------------------------------------------------

    def _ingest_document_files(
        self,
        file_paths: list[str],
        connection: Any,
        collection_name: str,
        batch_size: int,
        overwrite: bool,
        max_chunk_size: int,
        source_folder: str | None,
        result: IngestionResult,
        progress_callback: Callable[[int, int, str], None] | None,
    ) -> None:
        from vector_inspector.utils.lazy_imports import get_sentence_transformer

        model = get_sentence_transformer()

        batch_ids: list[str] = []
        batch_embeddings: list[list[float]] = []
        batch_documents: list[str] = []
        batch_metadatas: list[dict[str, Any]] = []

        def _flush() -> None:
            if batch_ids:
                count = len(batch_ids)
                ok = connection.add_items(
                    collection_name=collection_name,
                    ids=batch_ids[:],
                    embeddings=batch_embeddings[:],
                    documents=batch_documents[:],
                    metadatas=batch_metadatas[:],
                )
                batch_ids.clear()
                batch_embeddings.clear()
                batch_documents.clear()
                batch_metadatas.clear()
                if not ok:
                    raise RuntimeError(
                        f"Failed to write {count} chunk(s) to '{collection_name}' — see error log above for details"
                    )
                result.chunks_written += count

        for idx, path in enumerate(file_paths):
            if progress_callback:
                progress_callback(idx, len(file_paths), os.path.basename(path))

            file_hash: str | None = None
            try:
                # Validate
                if not os.path.isfile(path) or os.path.getsize(path) == 0:
                    result.failed += 1
                    result.errors.append(f"{path}: file not found or empty")
                    continue
                if not _is_document_file(path):
                    result.failed += 1
                    result.errors.append(f"{os.path.basename(path)}: unsupported file type")
                    continue

                file_hash = _md5(path)

                # Duplicate / partial ingestion check
                existing_count = _count_existing_chunks(connection, collection_name, file_hash)
                if existing_count > 0:
                    if overwrite:
                        _delete_chunks_by_parent(connection, collection_name, file_hash)
                    else:
                        stored_total = _get_stored_chunk_total(connection, collection_name, file_hash)
                        if stored_total is not None and existing_count >= stored_total:
                            result.skipped += 1
                            continue
                        # Partial ingestion — clean up and re-ingest
                        log_info(
                            "Partial ingestion detected for %s (%d/%s chunks). Re-ingesting.",
                            os.path.basename(path),
                            existing_count,
                            stored_total,
                        )
                        _delete_chunks_by_parent(connection, collection_name, file_hash)

                # Extract text
                full_text, page_count = _extract_text(path)
                full_text = full_text.strip()
                if not full_text:
                    result.failed += 1
                    result.errors.append(f"{os.path.basename(path)}: no extractable text")
                    continue

                char_count = len(full_text)
                word_count = len(full_text.split())

                # Chunk (compute chunk_total before any upsert)
                chunks = _chunk_text(full_text, max_chunk_size)
                chunk_total = len(chunks)

                filename = os.path.basename(path)
                common_meta: dict[str, Any] = {
                    "file_path": os.path.abspath(path),
                    "filename": filename,
                    "file_hash": file_hash,
                    "format": pathlib.Path(path).suffix.lstrip(".").lower(),
                    "file_type": "document",
                    "ingested_at": _utc_now(),
                    "char_count": char_count,
                    "word_count": word_count,
                    "chunk_total": chunk_total,
                    "parent_id": file_hash,
                }
                if page_count is not None:
                    common_meta["page_count"] = page_count
                if source_folder:
                    common_meta["source_folder"] = os.path.abspath(source_folder)

                # Embed and accumulate chunks
                chunk_upsert_failed = False
                chunks_upserted_this_file: list[str] = []

                for chunk_index, chunk_text in enumerate(chunks):
                    raw_embedding = model.encode(chunk_text).tolist()
                    embedding = _l2_normalize(raw_embedding)

                    chunk_id = f"{file_hash}-{chunk_index}"
                    chunk_meta = {**common_meta, "chunk_index": chunk_index}
                    doc_snippet = chunk_text[:512]

                    batch_ids.append(chunk_id)
                    batch_embeddings.append(embedding)
                    batch_documents.append(doc_snippet)
                    batch_metadatas.append(chunk_meta)
                    chunks_upserted_this_file.append(chunk_id)

                    if len(batch_ids) >= batch_size:
                        try:
                            _flush()
                        except Exception as exc:
                            chunk_upsert_failed = True
                            result.failed += 1
                            result.errors.append(f"{filename}: upsert failed at chunk {chunk_index}: {str(exc)[:200]}")
                            log_error(
                                "Document chunk upsert failed (%s chunk %d): %.300s", filename, chunk_index, str(exc)
                            )
                            # Clear pending batch and clean up already-flushed chunks
                            batch_ids.clear()
                            batch_embeddings.clear()
                            batch_documents.clear()
                            batch_metadatas.clear()
                            _delete_chunks_by_parent(connection, collection_name, file_hash)
                            break

                if chunk_upsert_failed:
                    continue

                # Flush remaining chunks
                try:
                    _flush()
                    result.succeeded += 1
                    log_info("Ingested document: %s (%d chunks)", filename, chunk_total)
                except Exception as exc:
                    result.failed += 1
                    result.errors.append(f"{filename}: final upsert failed: {str(exc)[:200]}")
                    log_error("Document final flush failed (%s): %.300s", filename, str(exc))
                    _delete_chunks_by_parent(connection, collection_name, file_hash)

            except Exception as exc:
                result.failed += 1
                result.errors.append(f"{os.path.basename(path)}: {exc}")
                log_error("Document ingestion failed for %s: %s", path, exc, exc_info=True)
                if file_hash:
                    _delete_chunks_by_parent(connection, collection_name, file_hash)

        if progress_callback:
            progress_callback(len(file_paths), len(file_paths), "")
