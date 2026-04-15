# Release Notes (0.7.2) — April 15, 2026

Major update: Enhanced error logging and telemetry for all vector DB providers, LLM providers, and core services. All critical errors now emit structured telemetry with category, operation, provider, and error type, while preserving full tracebacks in local logs for debugging.

## Error Logging & Telemetry
- All `log_error` calls in provider, LLM, and service layers upgraded to `log_tracked_error` with rich metadata (category, operation, provider, error_type, summary)
- All tracked errors now include `exc_info=True` for full traceback in logs (not sent to telemetry)
- Telemetry payloads are strictly metadata-only (no PII, no tracebacks)
- Centralized error tracking for ChromaDB, Qdrant, Pinecone, LanceDB, PgVector, Weaviate, and all LLM providers
- Service layer (data loaders, search, collection, backup/restore, import/export, settings, credentials, etc.) now emits structured error events
- Docstring and implementation of `log_tracked_error` updated to clarify safe usage and exc_info handling

## Internal
- 210+ call sites updated for consistent error tracking
- All tests pass (2129 passed, 3 skipped)

---
