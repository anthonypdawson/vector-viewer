## Release Notes (0.5.0)

### Fixes
- LanceDB provider fixes and improvements
	- Fix: `delete_items` now feature-detects the native LanceDB table delete API and uses it when available (`tbl.delete(predicate)`). If the native call raises, the implementation falls back to a safe rewrite.
	- Fix: Atomic rewrite fallback no longer double-inserts rows. The implementation now creates the table once with Arrow data (`create_table(data=arr)`) and avoids a subsequent `add()` call that caused duplicate inserts.
	- Test: Added unit tests covering the native delete path, fallback-on-error path, and a regression test to ensure the rewrite path does not double-add. See `tests/providers/test_lancedb_connection.py`.
	- Docs: Documented supported versions for `lancedb`/`pyarrow` in `README.md` and added a CI comment in `.github/workflows/ci-tests.yml` to flag where to look if version bumps break delete behavior.
	- Logging: Improved error logging around native delete failures to make fallback behavior easier to diagnose.

### Vector Visualization / Distributions

- Feature: Added a new "Distributions" tab to the Visualization view that renders histogram/distribution plots for vector norms and per-dimension values.
  - New: `HistogramPanel` at `src/vector_inspector/ui/views/visualization/histogram_panel.py` — UI controls (metric select, dimension index, bin count, density toggle, Generate, Clear) and Plotly-powered rendering into a `QWebEngineView`.
  - Feature: Compare overlay — enables side-by-side histogram comparison between collections across **all live connections**. The compare dropdown is populated via a background dim-scan thread that iterates every active `ConnectionInstance` (retrieved from `ConnectionManager`) and lists only collections sharing the same embedding dimensionality. Each entry is prefixed `"ConnectionName / collection"` for clarity. The scan runs fresh on every checkbox toggle so newly added connections are always reflected.
  - UI: `VisualizationView` now uses a `QTabWidget` with two tabs: **Visualization** (existing DR + plot + clustering panels) and **Distributions** (new histogram panel).
  - Integration: `VisualizationView` now calls `histogram_panel.set_data(data, collection_name, sample_size)` when collection data is loaded so the distributions tab auto-populates, `histogram_panel.set_connection(connection)` when the provider changes, and `histogram_panel.set_connection_manager(connection_manager)` at construction so the panel can scan all providers.
  - Architecture: `MainWindow` passes `connection_manager=self.connection_manager` to `VisualizationView`; `VisualizationView` stores it and forwards it to `HistogramPanel` after creation.

### Create Collection / Sample Data

- UX: `CreateCollectionDialog` now displays the active connection when opened and includes a `Randomize data` checkbox in the Sample Data options so users can choose deterministic or random sample content. See `src/vector_inspector/ui/components/create_collection_dialog.py`.
- Deterministic samples: Sample generators accept a `randomize: bool` flag (`generate_sample_data(..., randomize=False)`) to produce deterministic, index-based content useful for tests and reproducible demos. See `src/vector_inspector/core/sample_data/text_generator.py`.

---