# Release Notes (0.7.0) — 2026-04-01

## Ingestion
- New image ingestion pipeline: embed images with CLIP (`openai/clip-vit-base-patch32`, 512-dim) via "Import Images…" in the Import menu
- New document ingestion pipeline: embed text, PDF, Word, and source files with sentence-transformers (`all-MiniLM-L6-v2`, 384-dim) via "Import Documents…" in the Import menu
- Ingestion dialog includes folder/file picker, collection selector, "+ New collection" inline creation, overwrite toggle, batch size, and (for documents) max chunk size
- Documents are split into paragraph-aware chunks (1000 chars default); each chunk stored with `chunk_index`, `chunk_total`, `parent_id`, and file metadata
- Three-way duplicate detection: new files are ingested, fully-present files are skipped, partially-ingested files are cleaned up and re-ingested automatically
- "Re-ingest file…" context menu item in the metadata table re-ingests a single item's source file with `overwrite=True` when `file_path` metadata is present
- All lazy dependencies (`torch`, `transformers`, `Pillow`, `sentence-transformers`, `pypdf`, `python-docx`) imported on first use with clear install guidance if absent
- Loading dialog now shows the current filename and progress count (e.g. "Ingesting (3 of 42): report.pdf") while ingesting files
- Collection list refreshes automatically after ingestion creates a new collection — no manual refresh needed
- Per-file log entries restored: `Ingested image: <filename>` and `Ingested document: <filename> (N chunks)` logged on each successful file
- Ingestion fires `ingestion.started` telemetry at the beginning (file_kind, collection, file_count, overwrite, folder_mode) and `ingestion.completed` at the end (succeeded, skipped, failed, chunks_written, duration_ms)
- Completion-only log summary retained alongside per-file entries for quick status overview
- "Import Images…" and "Import Documents…" items added to the Connection menu for direct access without navigating to the Data tab
- New collection creation deferred to ingestion start and delegated to `CollectionService`; backends that don't support configurable vector size (e.g. ChromaDB) show a read-only dimension label

## File Preview
- Inline details pane: new collapsible "File Preview" section between Document Preview and Metadata
- Image thumbnails (160×120 in inline pane, 320×240 in details dialog) with filename label
- Text file previews: first 30 lines / 2 KB in inline pane, first 100 lines / 8 KB in details dialog, with truncation indicator
- Right-click context menu on preview images: "Open" (OS default viewer) and "Reveal in Explorer/Finder/Files"
- Double-click on preview image opens in OS default viewer
- Item details dialog: "File Preview" row between Document and Metadata with larger widgets
- Metadata table: new 📎 icon column at far left indicates rows with previewable file paths
- Preview detection via `find_preview_paths()`: scans candidate keys first, falls back to broader metadata scan, capped at 3 paths
- Text detection uses `mimetypes.guess_type` with null-byte sniff fallback (same heuristic as git)
- File preview section collapsed state persisted to settings

## Bug Fixes
- Fixed `_flush()` in both image and document ingestion pipelines: now checks `add_items` return value and raises on failure instead of silently losing data
- Fixed CLIP crash on small images: images below 3×3 pixels are rejected with a clear error instead of causing an ambiguous channel dimension error
- Fixed embedding nesting: `_l2_normalize` now flattens input to 1D, preventing 4D-nested embeddings that ChromaDB rejects
- Truncated error strings to 300–400 chars in ingestion pipelines and ChromaDB connection to prevent vector data from flooding logs
- Silenced verbose third-party loggers (`chromadb`, `sentence_transformers`, `transformers`, `httpx`, `httpcore`) at WARNING level

- Fixed UI crash when displaying metadata containing non-JSON-serializable types (e.g. `uuid.UUID` from Weaviate): added a sanitizer to ensure all metadata is safely rendered as JSON in details panes and dialogs.

---