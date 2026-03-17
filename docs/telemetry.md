# Vector Inspector — Telemetry Specification

This document defines the complete telemetry architecture for Vector Inspector, including event types, metadata schemas, privacy guarantees, sampling strategy, and integration patterns. It serves as the authoritative reference for all instrumentation across the application.

---

# 1. Goals

Vector Inspector’s telemetry system is designed to:

- Capture **meaningful, low-volume events** (errors, flows, UI actions) at 100%.
- Sample **high-volume events** (queries, embeddings) to control cost.
- Preserve user privacy by **never sending raw PII or secrets**.
- Provide **session-level visibility** and **flow-level correlation**.
- Enable reconstruction of user behavior for debugging and product insights.

---

# 2. Telemetry Architecture

Telemetry is handled by a singleton `TelemetryService`, initialized once at application startup.

### Automatically populated fields (never included manually):
- `hwid` — persistent client UUID
- `event_name`
- `app_version`
- `client_type` (`"vector-inspector"`)
- `created_at` — added by backend

### Cached context (auto-injected into metadata when available):
- `_cached_os`
- `_cached_hwid`
- `_cached_provider`
- `_cached_collection`

These values are set once or updated by the UI and automatically included in event metadata unless explicitly overridden.

TelemetryService behavior (implementation notes):
- The service caches immutable or rarely-changing values on startup to avoid repeated platform/settings calls: `_cached_os`, `_cached_hwid`.
- `hwid` is generated once and persisted to application settings under the key `telemetry.hwid`; the service returns the cached value thereafter.
- UI code sets session-scoped context via `TelemetryService.set_provider(provider_name)` and `TelemetryService.set_collection(collection_name)`; these are auto-injected into queued events.
- When all DB connections are closed the `ConnectionManager.close_connection()` flow clears the cached provider/collection (best-effort) to avoid stale context.
- Telemetry is disabled automatically when running under common test runners (e.g., pytest) to avoid noise during CI.
- Events are queued and sent in batches by a `send_batch` implementation which POSTs to the configured telemetry endpoint; batching and sampling behavior is documented in the code comments and config.

### Context propagation
- `session_id` — identifies a single GUI session
- `correlation_id` — identifies a single user flow (e.g., connection → query → visualization)

---

# 3. Event Inventory (Complete)

The following table lists all implemented telemetry events and their source files.

| Event Name | Category | File |
|------------|----------|------|
| `session.start` | Session | `src/vector_inspector/main.py` |
| `session.end` | Session | `src/vector_inspector/main.py` |
| `feature.toggled` | Features | `src/vector_inspector/extensions/telemetry_settings_panel.py` |
| `ui.collection_selected` | UI | `src/vector_inspector/ui/main_window.py` |
| `ui.table_view_opened` | UI | `src/vector_inspector/ui/views/metadata_view.py` |
| `ui.search_tab_opened` | UI | `src/vector_inspector/ui/main_window.py` |
| `ui.search_executed` | UI | `src/vector_inspector/ui/views/search_view.py` |
| `ui.table_row_selected` | UI | `src/vector_inspector/ui/views/search_view.py`, `metadata_view.py` |
| `ui.visualization_opened` | UI | `src/vector_inspector/ui/main_window.py` |
| `ui.visualization_interacted` | UI | `src/vector_inspector/ui/views/visualization/plot_panel.py` |
| `ui.embedding_preview_opened` | UI | `src/vector_inspector/ui/components/inline_details_pane.py` |
| `ui.settings_opened` | UI | `src/vector_inspector/ui/main_window.py` |
| `ui.refresh_triggered` | UI | `main_window.py`, `metadata_view.py`, `search_view.py` |
| `db.connection_attempt` | DB | `ui/controllers/connection_controller.py` |
| `db.connection_result` | DB | `ui/controllers/connection_controller.py` |
| `sample_db.create_started` | DB | `ui/workers/collection_worker.py` |
| `sample_db.create_completed` | DB | `ui/workers/collection_worker.py` |
| `sample_db.create_failed` | DB | `ui/workers/collection_worker.py` |
| `query.executed` | Query | `ui/views/search_view.py` |
| `embedding.request` | Embeddings | `core/connections/base_connection.py` |
| `clustering.run` | Analysis | `core/clustering.py` |
| `visualization.generated` | Analysis | `services/visualization_service.py` |
| `UncaughtException` | Errors | `utils/exception_handler.py` |
| `QtError` | Errors | `utils/exception_handler.py` |

---

# 4. Event Definitions

## 4.1 Session Events

### `session.start`
Emitted when the GUI becomes active.

**Metadata**
- session_id
- os
- app_version
- launch_source (`cli` | `desktop` | `vscode` | `unknown`)

---

### `session.end`
Emitted when the GUI closes.

**Metadata**
- session_id
- duration_ms
- exit_reason (`normal` | `crash` | `forced_close`)

---

## 4.2 UI Navigation & Interaction

### `ui.collection_selected`
Emitted when a collection is selected.

**Metadata**
- collection_name
- source (`sidebar` | `search_result`)

---

### `ui.table_view_opened`
Emitted when the metadata/table view loads.

**Metadata**
- collection_name
- row_count
- column_count
- triggered_by (`sidebar` | `search` | `visualization` | `other`)

---

### `ui.search_tab_opened`
Emitted when the user switches to the Search tab.

**Metadata**
- collection_name
- previous_tab
- has_existing_query (bool)

---

### `ui.search_executed`
Emitted when the user initiates a search.

**Metadata**
- collection_name
- query_length
- filters_used
- correlation_id

---

### `ui.table_row_selected`
Emitted when a row is selected.

**Metadata**
- collection_name
- row_id_hash (sha256 truncated; code uses `sha256(...).hexdigest()[:12]`)
- triggered_by (`click` | `keyboard`)

---

### `ui.visualization_opened`
Emitted when the Visualization tab loads.

**Metadata**
- collection_name
- embedding_dim
- projection_method
- point_count

---

### `ui.visualization_interacted`
Emitted when the user interacts with the visualization.

**Metadata**
- action (`select` | `zoom` | `pan` | `lasso`)
- selected_count
- collection_name

---

### `ui.embedding_preview_opened`
Emitted when a preview pane is shown.

**Metadata**
- collection_name
- row_id_hash
- preview_type (`inline` | `dialog`)

---

### `ui.settings_opened`
Emitted when the Settings dialog opens.

**Metadata**
- section

---

### `ui.refresh_triggered`
Emitted when the user refreshes data.

**Metadata**
- collection_name
- refresh_target (`collections` | `table` | `search_results`)

---

## 4.3 Database Operations

### `db.connection_attempt`
**Metadata**
- db_type
- host_hash
- connection_id
- correlation_id

**Hash truncation notes**
- `row_id_hash` in table/search/inline previews: `sha256(...).hexdigest()[:12]` (12 hex chars)
- `host_hash` / network identifiers: `sha256(...).hexdigest()[:16]` (16 hex chars)
- If other identifiers are added, prefer one of the above lengths and document it explicitly.

---

### `db.connection_result`
**Metadata**
- success
- db_type
- error_code
- error_class
- duration_ms
- correlation_id

---

### `sample_db.create_started`
**Metadata**
- db_type
- sample_db_id
- estimated_rows
- correlation_id

---

### `sample_db.create_completed`
**Metadata**
- success
- db_type
- sample_db_id
- rows_created
- duration_ms
- correlation_id

---

### `sample_db.create_failed`
**Metadata**
- db_type
- sample_db_id
- error_code
- retriable
- correlation_id

---

## 4.4 Query & Embedding Operations

### `query.executed`
**Metadata**
- query_type (`vector` | `metadata`)
- db_type
- result_count
- latency_ms
- filters_applied
- correlation_id

---

### `embedding.request`
**Metadata**
- provider
- model_id
- batch_size
- latency_ms
- error_code (optional)
- correlation_id

---

## 4.5 Visualization & Analysis

### `clustering.run`
**Metadata**
- algorithm
- params (summary)
- dataset_size
- duration_ms
- success
- correlation_id

---

### `visualization.generated`
**Metadata**
- method (`umap` | `pca` | `tsne`)
- dims
- points_rendered
- duration_ms
- success
- correlation_id

---

## 4.6 Error Events

### `UncaughtException`
**Metadata**
- message
- traceback (sanitized)
- exception_type
- correlation_id

---

### `QtError`
**Metadata**
- message
- msg_type
- file
- line
- function
- correlation_id

---

# 5. Common Metadata Fields

These fields appear across many events:

- `session_id`
- `correlation_id`
- `db_type`
- `duration_ms`
- `success`
- `error_code`
- `error_class`
- `os`

**Never include:**
`hwid`, `event_name`, `app_version`, `client_type` — these are auto-populated.

---

# 6. Privacy & PII Guidance

- Never send raw hostnames, usernames, API keys, or file paths.
- Hash identifiers using `sha256(...)` and truncate consistently per-field.
- Recommended defaults used in code:
	- `row_id_hash`: `sha256(...).hexdigest()[:12]`
	- `host_hash`: `sha256(...).hexdigest()[:16]`
	Document any deviation per-field to avoid ambiguity.
- Sanitize error messages to remove secrets.
- Use `error_hash` instead of full stack traces.
- Respect `settings.telemetry_enabled`.

---

# 7. Sampling & Retention

- Errors: **100%**
- UI events: **100%**
- Queries & embeddings: **1–5%** (record `sampling_rate`)
- Raw event retention: **7–30 days**
- Aggregated metrics: **90+ days**

---

# 8. Integration Patterns

- Generate `correlation_id` at the start of a flow.
- Pass it through async workers.
- Wrap telemetry calls in try/except.
- Use `send_batch()` when possible.
- Use `@exception_telemetry` for caught exceptions.

---

# 9. Code Examples

(Initialization, simple events, error events, decorators — unchanged from original.)

---

# 10. File Reference

- `services/telemetry_service.py` — core service
- `utils/exception_handler.py` — global exception hooks
- `ui/*` — UI event emitters
- `core/*` — backend operations

---

# 11. Best Practices Summary

1. Initialize once
2. Use try/finally
3. Generate correlation IDs early
4. Hash PII
5. Never block UI on telemetry
6. Batch events
7. Track success
8. Use ms precision
9. Let the service populate standard fields
