# Copilot Instructions for Vector Inspector & Vector Studio

Authoritative instructions live in the private pro repo:
`vector-studio/copilot-instructions.md`.



This file defines the rules Copilot must follow when assisting with
Vector Inspector (VI) and Vector Studio (VS). It establishes memory
policies, architectural boundaries, coding conventions, testing
patterns, and implementation rules. Copilot must treat this file as
the authoritative guide for all reasoning and code generation.

## 1. COPILOT’S ROLE & SCOPE

Copilot assists with:
- Vector Inspector (free-tier PySide6 desktop app)
- Vector Studio (premium extension layer)

Copilot must:
- Follow all rules in this file
- Respect VI/VS architectural boundaries
- Prefer existing patterns over inventing new ones
- Keep UI consistent with VI’s established design language
- Avoid speculative features or redesigns

Copilot must NOT:
- Create new UI surfaces in VS
- Move business logic into VI
- Introduce new dependencies without clear justification
- Invent color schemes or visual styles
- Break existing workflows or patterns

## 2. MEMORY PERSISTENCE POLICY

Vector Studio uses an MCP (Model Context Protocol) memory server for
persistent project knowledge. The Markdown file
`vector-studio/docs/copilot-working-notes.md` is a human-readable mirror.

- Transient learnings → stored in `vector-studio/docs/copilot-working-notes.md`
- Persistent memory → stored in the MCP server
- JSON mirrors → allowed only when tooling requires them

“When you are asked to persist memory, or you determine something is worth
persisting, you must record it in the MCP server, and then update the
Markdown file to reflect the current state.”

### 2.1 REQUIRED PERSISTENCE CHECKLIST (ALWAYS PRESENT)

Whenever a decision is made or new project information should be remembered:

1. Record to MCP  
   Structured observation with rationale, tags, ISO timestamp.

2. Mirror machine-readable (if required)  
   Update `vector-studio/docs/copilot-memory.json` (key, value, ts).

3. Regenerate human-readable  
   Update `vector-studio/docs/copilot-working-notes.md`.

4. Tag & Partition  
   Tags: `strategy`, `ux`, `policy`  
   Partition: `Vector Inspector` or `Vector Studio`  
   (never `vector-viewer`)

5. Commit message  
   `copilot-memory: add <short-key> — <summary>`

6. Confirm destructive changes  
   Ask before irreversible updates.

## 3. VI / VS ARCHITECTURAL BOUNDARIES & UI OWNERSHIP

This is one of the most important sections for Copilot.

### 3.1 UI OWNERSHIP MODEL

Vector Inspector (VI) owns ALL UI elements:
- All QActions, QMenus, QMenuItems, QToolButtons, QDockWidgets, QWidget controls
- All right‑click menu entries
- All toolbar and panel controls
- All disabled “Premium / Requires Vector Studio” stubs

Vector Studio (VS) MUST NOT create or duplicate UI controls.  
VS only injects behavior into existing VI controls.

### 3.2 DISABLED STUBS IN INSPECTOR

When a feature is Premium:
- VI creates the UI control
- VI disables it
- VI attaches tooltip: “Requires Vector Studio”
- VI connects the signal to a no‑op stub

Example pattern:

    actionViewSimilar.setEnabled(false);
    actionViewSimilar.setToolTip("Requires Vector Studio");
    connect(actionViewSimilar, QAction.triggered, this, MainWindow.premiumStub);

`premiumStub()` must do nothing except optionally show a simple “Requires Vector Studio” message.

### 3.3 STUDIO BEHAVIOR INJECTION

VS activates Premium features by:
- Locating the existing VI control (never creating a new one)
- Enabling it
- Disconnecting the stub slot
- Connecting the real implementation slot

VS MUST NOT:
- Modify VI UI layout
- Create new controls
- Duplicate menu entries

### 3.4 NO CROSS-LAYER LOGIC LEAKAGE

- VI contains no Premium logic.  
- VS contains no UI definitions.

All advanced workflows, algorithms, and implementations live in VS.  
All UI surfaces live in VI.

### 3.5 ABSOLUTE RULE

- Never duplicate a control.  
- Never move UI creation into VS.  
- Never place implementation logic in VI.  

## 4. CODING SAFETY RULES & CONVENTIONS

### 4.1 IMPORT STYLE

- Always use absolute imports within the project:
  `from vector_inspector.core.embedding_utils import ...`
- Prefer absolute imports over relative imports.
- Use relative imports only for very small, tightly-coupled internal modules
  when clearly justified.

### 4.2 EMBEDDING / ARRAY TRUTHINESS CHECKS

Never use direct truthiness checks on embeddings/vectors/arrays.

Use:

    from vector_inspector.utils import has_embedding

    embedding = item.get("embedding")
    if has_embedding(embedding):
        # safe to use embedding
        ...

Do NOT use:
- `if embedding:`
- `if vector:`
- `if not embedding:`

See `docs/EMBEDDING_TRUTHINESS.md` for detailed patterns and rationale.

### 4.3 LOGGING

- Use the project's logging utility (`vector_inspector.utils.logging`) for all logging.
- Never use raw `print()` or stdlib `logging` directly.
- Example:

    from vector_inspector.core.logging import log_info, log_error

### 4.4 LAZY IMPORTS

- Use `utils/lazy_imports.py` for heavy/optional dependencies
  (sklearn, plotly, umap-learn, hdbscan).
- Example:

    from vector_inspector.utils.lazy_imports import get_sklearn_model
    model = get_sklearn_model("PCA")

- Prevents slow startup times and allows graceful degradation if optional deps are missing.

### 4.5 TYPE ANNOTATIONS

- Use the built-in generic types with PEP 585 syntax (`list`, `dict`, `set`, `tuple`) for type annotations on Python 3.9+.
  - Example: prefer `foo: list[int]` and `bar: dict[str, Any]` over `typing.List` / `typing.Dict`.
  - Replace `from typing import List, Dict` usages with `list` / `dict` in annotations when targeting Python 3.9 or later.
  - Rationale: built-in generics are clearer, concise, and avoid deprecation warnings from `typing`.
  - Exception: continue to use `typing` constructs (e.g., `TypedDict`, `Protocol`, or `Literal`) when those specific types are required or when supporting older Python versions.

### 4.6 RUFF LINTING RULES

This project uses Ruff for linting and formatting. Keep these settings
synced with `pyproject.toml` so contributors and automation follow the
same rules.

- **Config (source: `pyproject.toml`)**

```toml
[tool.ruff]
line-length = 120
target-version = "py312"
extend-exclude = ["build", "dist", ".venv"]

[tool.ruff.format]
quote-style = "double"
indent-style = "space"
line-ending = "auto"
skip-magic-trailing-comma = false

[tool.ruff.lint]
select = [
    "E", "F", "W", "I", "UP", "B", "A", "C4", "DTZ",
    "T20", "RET", "SIM", "ARG", "RUF",
]
ignore = ["E501", "I001", "UP045", "SIM105"]

[tool.ruff.lint.isort]
combine-as-imports = true
known-first-party = ["vector_inspector"]
```

- **Quick rules summary**
  - **Line length:** 120 characters.
  - **Target Python:** 3.12 (`py312`) — runtime still supports >=3.11.
  - **Excludes:** `build`, `dist`, `.venv`.
  - **Formatting:** prefer double quotes, use spaces for indentation, platform line endings.
  - **Ignored rules:** `E501` (line length enforced by config), `I001`, `UP045`, `SIM105`.
  - **isort:** combine `as` imports and treat `vector_inspector` as first-party.

**Selected rule groups (human-readable)**

- `E`: pycodestyle (PEP 8) errors — style errors such as indentation, spacing, and other PEP 8 violations.
- `F`: pyflakes checks — static issues like undefined names and unused imports.
- `W`: pycodestyle warnings — non-fatal style warnings.
- `I`: `isort` import-order and grouping checks.
- `UP`: pyupgrade rules — automatic Python syntax modernizations (e.g., prefer f-strings, modern dict/set syntax).
- `B`: Bugbear plugin — heuristics catching likely bugs and suboptimal patterns.
- `A`: annotation checks (flake8-annotations style) — enforces presence/consistency of type annotations.
- `C4`: complexity-related checks — code complexity metrics and related concerns.
- `DTZ`: documentation/typing helpers (plugin group) — docstring/typing-related lint checks (project uses the DTZ group where applicable).
- `T20`: typing/typing-safety checks (plugin group) — additional type-related checks gathered by Ruff plugins.
- `RET`: return-value / early-return related checks — rules about return usage and control-flow returns.
- `SIM`: simplification suggestions — replace complex constructs with simpler equivalents (e.g., simplify boolean expressions, comprehensions).
- `ARG`: argument-related checks — issues with function arguments (shadowing, unused args, incorrect defaults).
- `RUF`: Ruff-specific rules — core Ruff rules that don't map to upstream tools.

**Ignored rule examples (why they're suppressed)**

- `E501`: line-length — intentionally ignored because `line-length` is enforced centrally via the `line-length` setting.
- `I001`: isort startup/internal informational message — suppressed to avoid noisy diagnostics.
- `UP045`: a specific pyupgrade rule chosen to be ignored in this codebase.
- `SIM105`: a specific simplification rule that the team has chosen not to enforce.

If you want the full, line-by-line meaning for any of these codes (for example `SIM105` or `UP045`), ask Copilot which ones and it will provide the exact rule description and rationale.

If you update these settings in `pyproject.toml`, please mirror the change here.

## 5. TESTING RULES (PYTEST + QT)

### 5.1 Running Tests

    pdm run pytest --cov=vector_inspector --cov-report=html
    pdm run pytest tests/test_metadata_navigation.py
    pdm run pytest -n auto
    QT_QPA_PLATFORM=offscreen pdm run pytest

- Tests use `pytest` with `pytest-qt` for Qt widget testing.
- `tests/conftest.py` provides `fake_provider` fixture — a mock vector DB for isolated testing.

### 5.2 Organization

- Tests should be organized by feature, not by type.
  - Good: `test_plot_selection.py` contains all plot selection tests (with and without Qt).
  - Bad: separate `test_plot_selection_qt.py` and `test_plot_selection_unit.py`.

### 5.3 Qt & Providers

- Always use `qtbot` for Qt signal/slot testing, even for simple signal emission checks.
- Use `qtbot` for any test involving Qt widgets, signals, or user interactions.
- Testing with fake providers:

    def test_something(fake_provider):
        # fake_provider comes pre-populated with test_collection
        result = fake_provider.get_all_items("test_collection")
        assert result["ids"] == ["id1", "id2", "id3"]

- Use `empty_fake_provider` fixture when testing "no data" scenarios.
- Mock `ConnectionInstance` when testing UI components.
- CI uses `QT_QPA_PLATFORM=offscreen` for headless Qt testing.

## 6. PROJECT OVERVIEW & ARCHITECTURE

### 6.1 Project Overview

- Vector Inspector is a PySide6 (Qt for Python) desktop app for visualizing,
  querying, and managing data in multiple vector database backends
  (ChromaDB, Qdrant, Pinecone, Milvus, LanceDB, PgVector, etc.).
- The app provides a SQL-database-viewer-like GUI for vector DBs, supporting
  dimensionality reduction, clustering, metadata filtering, and interactive plots.
- The codebase is modular, with clear separation between UI (Qt widgets),
  business logic (services), and provider-specific data access (core/connections).

### 6.2 Three-Layer Architecture

UI Layer (`src/vector_inspector/ui/`):
- Qt widgets and views.
- `views/` → main screens (e.g., `metadata_view.py`, `visualization_view.py`).
- `components/` → reusable dialogs and widgets (e.g., `item_details_dialog.py`,
  `loading_dialog.py`).
- Complex views use submodules (e.g., `ui/views/metadata/` for table, threads, I/O, filters).

Service Layer (`src/vector_inspector/services/`):
- Business logic, no Qt dependencies.
- Examples: `visualization_service.py` (DR/clustering),
  `backup_restore_service.py`, `filter_service.py`.

Core Layer (`src/vector_inspector/core/`):
- Provider abstractions and connection management.
- `connections/` → each provider implements `VectorDBConnection`.
- `connection_manager.py` → `ConnectionInstance` proxy via `__getattr__`.
- `cache_manager.py` → caches data by (database, collection) key.

### 6.3 Data Flow Pattern

1. UI view calls `ConnectionInstance` method (e.g., `get_all_items()`).
2. `ConnectionInstance.__getattr__` forwards to the provider’s `VectorDBConnection`.
3. Service layer processes results (DR, clustering, etc.).
4. Results returned to UI for visualization (Plotly via `QWebEngineView` or matplotlib).

## 7. PROJECT CONVENTIONS

### 7.1 Provider Abstraction

- Never call provider SDKs directly in UI or services — always use `ConnectionInstance`.
- All providers implement `VectorDBConnection` (see `core/connections/base_connection.py`).
- `ConnectionInstance.__getattr__` forwards unknown methods to the underlying `database`.
- Example: `connection.get_all_items()` → `ChromaDBConnection.get_all_items()`.
- Profile names are injected onto connections: `self.database.profile_name = name`.

### 7.2 UI Design Patterns

- Keep views thin: business logic belongs in services, not Qt widgets.
- Double-click = view (read-only): table double-clicks open read-only details dialog.
- Right-click → edit: editing is explicit via context menu, not double-click.
- Inline details pane (metadata & search views):
  - Collapsible bottom pane.
  - Updates on row selection (not just double-click).
  - Shows header bar, document preview, collapsible metadata/vector sections.
  - Remembers collapsed/expanded state and splitter height via settings.
  - “Open full details” button opens the modal dialog.
  - See `ui/components/inline_details_pane.py` for implementation.
- Background loading: use QThread subclasses (see `metadata_threads.py`) for long operations.
- Context menus: use extension hooks for pro features — see `extensions/__init__.py`.

### 7.3 Cache Management

- `CacheManager` stores per-(database, collection) state: data, scroll position,
  filters, search query.
- Cache keys: `(database_name, collection_name)` tuples.
- Invalidation: call `cache_manager.invalidate(db, coll)` after mutations.
- Always check `cache_manager.get(db, coll)` before loading from DB.
- See `metadata_view.py` `set_collection()` for cache hit/miss pattern.

### 7.4 Signal/Slot Patterns (Qt)

- Connect signals to private methods:
  `button.clicked.connect(self._on_click)`.
- Use lambda for parameterized slots:
  `action.triggered.connect(lambda: self._export("json"))`.
- Thread signals:
  `thread.finished.connect(self._on_complete)` and `thread.error.connect(self._on_error)`.
- Debouncing: use `QTimer.singleShot()` for delayed actions (e.g., filter changes).

### 7.5 Settings & Paths

- User settings: `~/.vector-inspector/settings.json` (managed by `SettingsService`).
- Relative paths: resolved from project root (where `pyproject.toml` is).
- Example: `./data/chroma_db` → absolute path computed from root.
- Connection configs: saved to settings on disconnect, auto-restored on startup.

### 7.6 Logging (Project-Level)

- Always use `vector_inspector.utils.logging`.
- Never use `print()` or stdlib `logging` directly.
- Ensures consistent formatting and easier log redirection.

## 8. EXTENSION SYSTEM (VECTOR STUDIO)

- Hook pattern: pro features register handlers without modifying free code.
- `table_context_menu_hook.register(handler)` → adds custom menu items to table context menus.
- `settings_panel_hook.register(handler)` → adds custom sections to Settings dialog.
- Example: Vector Studio adds “Find Similar” via `table_context_menu_hook`.
- Handlers are exception-safe: failures are logged but do not crash the app.

## 9. COMMON IMPLEMENTATION PATTERNS

### 9.1 Adding a New Vector DB Provider

1. Create `src/vector_inspector/core/connections/yourprovider_connection.py`.
2. Subclass `VectorDBConnection` and implement abstract methods.
3. Register in `core/connections/provider_factory.py`.
4. Add connection UI in `ui/components/connection_dialog.py`.
5. Follow examples like `lancedb_connection.py` or `pgvector_connection.py`.

### 9.2 Adding a Clustering Algorithm

1. Extend `core/clustering.py` `run_clustering()` function.
2. Add lazy import in `utils/lazy_imports.py` if new dependency.
3. Update `VisualizationView` dropdown options.
4. Follow HDBSCAN integration as a reference.

### 9.3 Modifying Table Behavior

- Table population: edit `ui/views/metadata/metadata_table.py` `populate_table()`.
- Context menu: add items in `show_context_menu()` or use extension hooks.
- Double-click: handled by view’s `_on_row_double_clicked()` method.
- In-place updates: use `update_row_in_place()` to refresh single rows without full reload.

### 9.4 Background Data Loading (QThread Pattern)

1. Create QThread subclass in `metadata_threads.py` (or similar).
2. Emit `finished` signal with data, `error` signal with error message.
3. Connect signals in view:

       thread.finished.connect(self._on_data_loaded)
       thread.error.connect(self._on_error)

4. Show `LoadingDialog` while thread runs:

       self.loading_dialog.show_loading("Message")

5. Hide the loading dialog in both success and error handlers.
6. Threads must not modify UI directly; views handle UI updates.
7. Parent threads to the view and clean them up after completion.
8. Never reuse thread instances.
9. Example: see `DataLoadThread` in `metadata_threads.py`.

### 9.5 Adding Inline Details to a View

1. Import `InlineDetailsPane` from `ui/components/inline_details_pane.py`.
2. Create pane with mode:

       self.details_pane = InlineDetailsPane(view_mode="data_browser")
       # or "search"

3. Add to splitter as bottom section:

       splitter.addWidget(self.details_pane)

4. Connect row selection:

       table.itemSelectionChanged.connect(self._on_selection_changed)

5. Update pane in selection handler:

       self.details_pane.update_item(item_data)

6. Connect full details signal:

       self.details_pane.open_full_details.connect(self._open_full_details_from_pane)

7. Save splitter sizes on move:

       splitter.splitterMoved.connect(lambda: self._save_splitter_sizes(splitter))

8. Save pane state on close: implement `closeEvent` that calls `self.details_pane.save_state()`.
9. See `metadata_view.py` or `search_view.py` for full examples.

## 10. DEVELOPER WORKFLOWS

### 10.1 Install & Run

    pip install pdm
    pdm install -d
    pdm run python -m vector_inspector

    ./scripts/run.sh      # Linux/macOS
    ./scripts/run.bat     # Windows

### 10.2 Build & Release

- PyPI upload: `./pypi-upload.sh` (requires `~/.pypirc`).
- Versioning: managed by `bumpver` (see `bumpver.toml`).
- CI/CD: GitHub Actions in `.github/workflows/`:
  - `ci-tests.yml` → tests on push/PR.
  - `release-and-publish.yml` → publishes to PyPI on tags.
  - `nuitka.yml` → experimental native compilation.

## 11. RELEASE NOTES

All release notes are added in `docs/RELEASE_REASON.md`, not in this file.  
This file is cleared when the version is incremented and a new release is created.

## 12. REFERENCES

- `docs/architecture.md` — high-level diagram and rationale.
- `README.md` — install, usage, feature overview.
- `docs/artifact_resolution.md` — LLM-based similarity explanation design.

## 13. AUTHORITATIVE NOTE

Authoritative instructions live in the private pro repo:
`vector-studio/copilot-instructions.md`.