---
applyTo: "src/**"
---

# Coding Conventions

These rules apply when working in the `src/` directory.

## Ruff Linting Rules

This project uses Ruff for linting and formatting. Keep these settings
synced with `pyproject.toml` so contributors and automation follow the
same rules.

**Config (source: `pyproject.toml`)**

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

**Quick rules summary**
- **Line length:** 120 characters.
- **Target Python:** 3.12 (`py312`) — runtime still supports >=3.11.
- **Excludes:** `build`, `dist`, `.venv`.
- **Formatting:** prefer double quotes, use spaces for indentation, platform line endings.
- **Ignored rules:** `E501` (line length enforced by config), `I001`, `UP045`, `SIM105`.
- **isort:** combine `as` imports and treat `vector_inspector` as first-party.
- **typehints:** Use PEP 585 style (use list instead of List and dict instead of Dict).

**Selected rule groups (human-readable)**

- `E`: pycodestyle (PEP 8) errors — style errors such as indentation, spacing, and other PEP 8 violations.
- `F`: pyflakes checks — static issues like undefined names and unused imports.
- `W`: pycodestyle warnings — non-fatal style warnings.
- `I`: `isort` import-order and grouping checks.
- `UP`: pyupgrade rules — automatic Python syntax modernizations (e.g., prefer f-strings, modern dict/set syntax).
- `B`: Bugbear plugin — heuristics catching likely bugs and suboptimal patterns.
- `A`: annotation checks (flake8-annotations style) — enforces presence/consistency of type annotations.
- `C4`: complexity-related checks — code complexity metrics and related concerns.
- `DTZ`: documentation/typing helpers (plugin group) — docstring/typing-related lint checks.
- `T20`: typing/typing-safety checks (plugin group) — additional type-related checks gathered by Ruff plugins.
- `RET`: return-value / early-return related checks — rules about return usage and control-flow returns.
- `SIM`: simplification suggestions — replace complex constructs with simpler equivalents.
- `ARG`: argument-related checks — issues with function arguments (shadowing, unused args, incorrect defaults).
- `RUF`: Ruff-specific rules — core Ruff rules that don't map to upstream tools.

**Ignored rule examples (why they're suppressed)**

- `E501`: line-length — intentionally ignored because `line-length` is enforced centrally via the `line-length` setting.
- `I001`: isort startup/internal informational message — suppressed to avoid noisy diagnostics.
- `UP045`: a specific pyupgrade rule chosen to be ignored in this codebase.
- `SIM105`: a specific simplification rule that the team has chosen not to enforce.

If you update these settings in `pyproject.toml`, please mirror the change here.

## Error Handling Convention

Follow these layer-specific rules so errors surface cleanly without leaking implementation details into the UI or swallowing failures silently.

- **Service layer** — raise exceptions; do not catch broadly. Let the caller decide how to present the error.
- **QThread workers** — catch exceptions in `run()` and emit the `error` signal with a plain string message. Never modify the UI from a thread.
- **UI layer** — connect the worker's `error` signal to a handler that shows `QMessageBox.critical()` or updates a status label. Handle only specific, expected exceptions; do not catch exceptions broadly (avoid `except Exception:`). Log events with the project's logging utility (include `exc_info=True` for unexpected errors) and send telemetry only after redacting PII. The user-facing message should be clear and actionable without technical jargon or stack traces. For unexpected exceptions, log full details with a correlation id and show a generic error message to the user.

- **User-facing error messaging rule (UI policy)** — When surfacing errors to users from the UI:
    - Show a short, descriptive, and user-friendly message in the visible UI (for example: "Connection failed — hover for details" or "Could not reach model server — check console"). Keep the visible text concise while still conveying actionable guidance.
    - If the UI does not present a modal dialog with the full diagnostic, make the detailed message available via a widget tooltip (e.g., `QLabel.setToolTip(...)`) so users can view the full diagnostic on hover.
    - Always send the full error/exception details to the application logs (use `vector_inspector.core.logging.log_error`) including stack/exception info where appropriate (`exc_info=True`) so developers can troubleshoot. Redact any PII before logging.
    - Prefer concise visible messages to avoid resizing or confusing UI, and place only non-sensitive, actionable guidance in the visible message. The visible message should, where appropriate, explicitly guide users to the tooltip or console for full details.

    Example pattern:

```python
from vector_inspector.core.logging import log_error

def _on_error(self, full_message: str, visible: str | None = None) -> None:
        # visible: short descriptive guidance shown to user; full_message: detailed diagnostic
        short = visible or "Operation failed — hover for details"
        self.status_label.setText(short)
        self.status_label.setToolTip(full_message)
        # Log full details for developers (include exception info when available)
        log_error("Operation failed: %s", full_message)
        # Use a modal only when immediate acknowledgement is required
        # QMessageBox.critical(self, "Error", short)
```
- **Extension hooks** — wrap handler calls in `try/except` and log failures; do not let a plugin crash the main app.
- **Top-level unhandled exceptions** — covered by `vector_inspector.utils.exception_handler`; no additional handling needed.

```python
# Typical QThread -> view error flow
thread.error.connect(self._on_error)

def _on_error(self, message: str) -> None:
    self.loading_dialog.hide()
    QMessageBox.critical(self, "Error", message)
```

## UI Design Patterns

- Keep views thin: business logic belongs in services, not Qt widgets.
- Double-click = view (read-only): table double-clicks open read-only details dialog.
- Right-click -> edit: editing is explicit via context menu, not double-click.
- Inline details pane (metadata & search views):
  - Collapsible bottom pane.
  - Updates on row selection (not just double-click).
  - Shows header bar, document preview, collapsible metadata/vector sections.
  - Remembers collapsed/expanded state and splitter height via settings.
  - "Open full details" button opens the modal dialog.
  - See `ui/components/inline_details_pane.py` for implementation.
- Background loading: use QThread subclasses (see `metadata_threads.py`) for long operations.
- Context menus: use extension hooks for pro features — see `extensions/__init__.py`.

## Cache Management

- `CacheManager` is a singleton service that stores per-(database, collection) state:
  data, scroll position, filters, search query.
- Access via `app_state.cache_manager` (preferred) or `CacheManager()` (deprecated).
- Cache keys: `(database_name, collection_name)` tuples.
- Invalidation: call `app_state.cache_manager.invalidate(db, coll)` after mutations.
- Always check `app_state.cache_manager.get(db, coll)` before loading from DB.
- See `metadata_view.py` `set_collection()` for cache hit/miss pattern.

```python
# Preferred
cached_entry = self.app_state.cache_manager.get(database, collection)
if cached_entry:
    self.populate_table(cached_entry.data)
else:
    data = self.app_state.provider.get_all_items(collection)
    self.app_state.cache_manager.set(database, collection, CacheEntry(data=data))
```

## AppState Pattern (Centralized State Management)

Vector Inspector uses `AppState` as a centralized state container for application-wide services and state.

**Core Services (Singleton Pattern)**

Three core services use singleton pattern to prevent state inconsistencies:

1. `SettingsService` - Application settings persistence
2. `CacheManager` - Per-(database, collection) caching
3. `EmbeddingModelRegistry` - Known embedding models registry

Each service implements singleton via `__new__`:

```python
class SettingsService:
    _instance: 'SettingsService | None' = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if '_initialized' in self.__dict__:
            return
        self._initialized = True
        # ... initialization code
```

All UI views and components should receive `app_state` as a required parameter:

```python
class MetadataView(QWidget):
    def __init__(self, app_state: AppState, task_runner: ThreadedTaskRunner):
        super().__init__()
        self.app_state = app_state
        self.task_runner = task_runner
```

**DO NOT** use `Optional[AppState]` with fallback logic — this is legacy code that should be removed.

**Accessing Services** — prefer `app_state` properties over direct instantiation:

```python
# PREFERRED
settings = self.app_state.settings_service
cache = self.app_state.cache_manager
registry = self.app_state.model_registry
provider = self.app_state.provider

# DEPRECATED (but still works due to singleton)
settings = SettingsService()
cache = get_cache_manager()
```

**Signal-Based Reactivity**

```python
app_state.connection_changed.connect(self._on_connection_changed)
app_state.collection_changed.connect(self._on_collection_changed)
app_state.settings_service.signals.setting_changed.connect(self._on_setting_changed)
```

**Feature Flags**

```python
if self.app_state.advanced_features_enabled:
    self.hdbscan_option.setEnabled(True)
```

**Backward Compatibility** — deprecated helpers (new code must use `app_state.*`):
- `get_settings_service()` returns `SettingsService()` singleton
- `get_cache_manager()` returns `CacheManager()` singleton
- `get_model_registry()` returns `EmbeddingModelRegistry()` singleton

**Testing — singleton reset for isolation:**

```python
def test_something():
    SettingsService._instance = None
    SettingsService._initialized = False
    service = SettingsService()
```

**Migration Note:** The codebase has been migrated from optional AppState parameters to required parameters.
All views now require `app_state: AppState` with no `Optional` type or legacy fallback code.

## Signal/Slot Patterns (Qt)

- Connect signals to private methods: `button.clicked.connect(self._on_click)`.
- Use lambda for parameterized slots: `action.triggered.connect(lambda: self._export("json"))`.
- Thread signals: `thread.finished.connect(self._on_complete)` and `thread.error.connect(self._on_error)`.
- Debouncing: use `QTimer.singleShot()` for delayed actions (e.g., filter changes).

## Settings & Paths

- `SettingsService` is a singleton for application settings persistence.
- Access via `app_state.settings_service` (preferred) or `SettingsService()` (deprecated).
- User settings stored in: `~/.vector-inspector/settings.json`.
- Relative paths: resolved from project root (where `pyproject.toml` is).
- Example: `./data/chroma_db` -> absolute path computed from root.
- Connection configs: saved to settings on disconnect, auto-restored on startup.

```python
# Preferred
last_connection = self.app_state.settings_service.get_last_connection()
self.app_state.settings_service.save_last_connection(config)
self.app_state.settings_service.signals.setting_changed.connect(self._on_setting_changed)
```

## Logging (Project-Level)

- Always use `vector_inspector.utils.logging`.
- Never use `print()` or stdlib `logging` directly.
- Ensures consistent formatting and easier log redirection.

## ThreadedTaskRunner

`ThreadedTaskRunner` (`vector_inspector.services.task_runner`) is the standard way to run background work
across the app. It is a `QObject` (not a `QThread`) that manages a pool of `TaskRunner` threads internally.

**When to use it vs raw QThread subclasses:**
- Use `ThreadedTaskRunner.run_task()` for one-off or simple background functions (fetching data, calling an API, running a computation).
- Use a dedicated `QThread` subclass (e.g. `DataLoadThread`, `SearchThread`) only when the background task requires complex state, incremental progress emission, or custom cancellation logic that doesn't fit the generic callback model.

**Usage:**

```python
self.task_runner.run_task(
    my_function,                       # plain callable — runs in background thread
    arg1, arg2,                        # positional args forwarded to my_function
    task_id="my-task",                 # optional; cancels any prior task with the same id
    on_finished=self._on_done,         # called with the return value on success
    on_error=self._on_error,           # called with error string on exception
    on_progress=self._on_prog,         # called with (message, percent) if task reports progress
)
```

- All views receive `task_runner: ThreadedTaskRunner` as a constructor parameter alongside `app_state`.
  Create one instance per top-level window and pass it down.
- `TaskRunner` (the underlying thread) emits `result_ready`, `error`, and `progress` signals and auto-cleans up after itself.
- Call `task_runner.cancel_task(task_id)` to abort a running task; call `cancel_all()` on shutdown.

## Extension System (Vector Studio)

- Hook pattern: pro features register handlers without modifying free code.
- `table_context_menu_hook.register(handler)` adds custom menu items to table context menus.
- `settings_panel_hook.register(handler)` adds custom sections to the Settings dialog.
- Example: Vector Studio adds "Find Similar" via `table_context_menu_hook`.
- Handlers are exception-safe: failures are logged but do not crash the app.

## Common Implementation Patterns

### Adding a New Vector DB Provider

1. Create `src/vector_inspector/core/connections/yourprovider_connection.py`.
2. Subclass `VectorDBConnection` and implement abstract methods.
3. Register in `core/connections/provider_factory.py`.
4. Add connection UI in `ui/components/connection_dialog.py`.
5. Follow examples like `lancedb_connection.py` or `pgvector_connection.py`.

### Adding a Clustering Algorithm

1. Extend `core/clustering.py` `run_clustering()` function.
2. Add lazy import in `utils/lazy_imports.py` if new dependency.
3. Update `VisualizationView` dropdown options.
4. Follow HDBSCAN integration as a reference.

### Modifying Table Behavior

- Table population: edit `ui/views/metadata/metadata_table.py` `populate_table()`.
- Context menu: add items in `show_context_menu()` or use extension hooks.
- Double-click: handled by view's `_on_row_double_clicked()` method.
- In-place updates: use `update_row_in_place()` to refresh single rows without full reload.

### Background Data Loading (QThread Pattern)

1. Create QThread subclass in `metadata_threads.py` (or similar).
2. Emit `finished` signal with data, `error` signal with error message.
3. Connect signals in view:

       thread.finished.connect(self._on_data_loaded)
       thread.error.connect(self._on_error)

4. Show `LoadingDialog` while thread runs: `self.loading_dialog.show_loading("Message")`.
5. Hide the loading dialog in both success and error handlers.
6. Threads must not modify UI directly; views handle UI updates.
7. Parent threads to the view and clean them up after completion.
8. Never reuse thread instances.
9. Example: see `DataLoadThread` in `metadata_threads.py`.

### Adding Inline Details to a View

1. Import `InlineDetailsPane` from `ui/components/inline_details_pane.py`.
2. Create pane with mode: `self.details_pane = InlineDetailsPane(view_mode="data_browser")`.
3. Add to splitter as bottom section: `splitter.addWidget(self.details_pane)`.
4. Connect row selection: `table.itemSelectionChanged.connect(self._on_selection_changed)`.
5. Update pane in selection handler: `self.details_pane.update_item(item_data)`.
6. Connect full details signal: `self.details_pane.open_full_details.connect(self._open_full_details_from_pane)`.
7. Save splitter sizes on move: `splitter.splitterMoved.connect(lambda: self._save_splitter_sizes(splitter))`.
8. Save pane state on close: implement `closeEvent` that calls `self.details_pane.save_state()`.
9. See `metadata_view.py` or `search_view.py` for full examples.
