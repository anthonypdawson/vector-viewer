# Vector Inspector 0.7.0 — April 5, 2026  
A major milestone release introducing **full text and image ingestion**, **multimodal embeddings**, and **inline file previews**.  
You can now build real multimodal collections, inspect their embeddings, and run text→image semantic search directly inside Vector Inspector.

---

# 🚀 Highlights

### **✓ Multimodal Ingestion (Images + Documents)**
Import images, text files, PDFs, Word docs, and source files into any collection.  
Images are embedded with CLIP (512‑dim).  
Documents are chunked and embedded with MiniLM (384‑dim).

### **✓ Text → Image Semantic Search**
You can now type a natural‑language query and retrieve matching images from your collection using CLIP’s shared embedding space.

### **✓ Inline File Previews**
Images and text files now show thumbnails or text snippets directly in the details pane and item dialog, making it easy to verify ingestion and debug metadata.

### **✓ Robust, Production‑Ready Ingestion Pipeline**
Chunking, duplicate detection, partial‑ingest recovery, and detailed logging ensure ingestion is deterministic, resumable, and transparent.

---

# 🧩 Ingestion

- **Image ingestion pipeline** using CLIP (`openai/clip-vit-base-patch32`, 512‑dim)  
- **Document ingestion pipeline** using sentence-transformers (`all-MiniLM-L6-v2`, 384‑dim)  
- Import via **“Import Images…”** and **“Import Documents…”** in the Tools menu  
- Paragraph‑aware chunking for documents (1000 chars default) with `chunk_index`, `chunk_total`, `parent_id`, and file metadata  
- **Three‑way duplicate detection:**  
  - new files ingested  
  - fully-present files skipped  
  - partially-ingested files automatically cleaned and re‑ingested  
- **Re-ingest file…** context menu option for single-file overwrite  
- Lazy loading of heavy dependencies with clear install guidance  
- Ingestion dialog shows filename + progress (e.g. “3 of 42”)  
- Collections auto-refresh after ingestion  
- Per-file log entries restored (`Ingested image: …`, `Ingested document: …`)  
- Telemetry: `ingestion.started` and `ingestion.completed` with full metrics  
- New collections created at ingestion time via `CollectionService`  
- Backends without configurable vector size show read-only dimension label  

---

# 🖼️ File Preview

- New **File Preview** section in the inline details pane  
- Image thumbnails:  
  - 160×120 inline  
  - 320×240 in item dialog  
- Text previews:  
  - 30 lines / 2 KB inline  
  - 100 lines / 8 KB in dialog  
- Right-click actions: **Open** and **Reveal in Explorer/Finder/Files**  
- Double-click image → open in OS viewer  
- Metadata table now shows a 📎 icon for rows with previewable files  
- Preview detection via `find_preview_paths()` with safe fallbacks  
- Text detection via `mimetypes.guess_type` + null-byte sniff  
- Collapsed state persisted in settings  

---

# 🛠️ Bug Fixes & Stability

- Fixed `_flush()` in ingestion pipelines to correctly detect and raise on failed writes  
- Fixed CLIP crash on tiny images (<3×3 px) with a clear error message  
- Fixed embedding nesting: `_l2_normalize` now flattens to 1D  
- Truncated long error strings to avoid log flooding  
- Silenced noisy third‑party loggers (`chromadb`, `sentence_transformers`, etc.)  
- Fixed UI crash when metadata contained non‑JSON‑serializable types (e.g. `uuid.UUID`) via a new metadata sanitizer  

---

# 🎉 Summary

0.7.0 transforms Vector Inspector into a **true multimodal semantic debugging tool**.  
You can now ingest real documents and images, inspect their embeddings, preview their contents, and run text→image semantic search — all with a stable, production‑grade ingestion pipeline.

---
