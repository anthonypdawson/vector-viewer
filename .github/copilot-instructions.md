# Copilot Instructions for Vector Inspector

This file defines the **core rules** Copilot must follow at all times when working in Vector Inspector.
Detailed conventions are in scoped instruction files that load automatically based on context:

- `.github/instructions/coding.instructions.md` — Ruff config, error handling, UI patterns, AppState,
  ThreadedTaskRunner, settings, cache, extension hooks, common implementation patterns (`src/**`)
- `.github/instructions/testing.instructions.md` — pytest/Qt rules, fixtures, coverage target,
  directory structure, conftest conventions (`tests/**`)
- `.github/instructions/workflows.instructions.md` — install/run, PDM dependency management,
  build/release, release notes format (`**`)

## 1. COPILOT'S ROLE & SCOPE

Copilot assists with:
- Vector Inspector (free-tier PySide6 desktop app)
- Vector Studio (premium extension layer)

Copilot must:
- Follow all rules in this file
- Respect VI/VS architectural boundaries
- Prefer existing patterns over inventing new ones
- Keep UI consistent with VI's established design language
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

- Transient learnings -> stored in `vector-studio/docs/copilot-working-notes.md`
- Persistent memory -> stored in the MCP server
- JSON mirrors -> allowed only when tooling requires them

"When you are asked to persist memory, or you determine something is worth
persisting, you must record it in the MCP server, and then update the
Markdown file to reflect the current state."

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
- All right-click menu entries
- All toolbar and panel controls
- All disabled "Premium / Requires Vector Studio" stubs

Vector Studio (VS) MUST NOT create or duplicate UI controls.
VS only injects behavior into existing VI controls.

### 3.2 DISABLED STUBS IN INSPECTOR

When a feature is Premium:
- VI creates the UI control
- VI disables it
- VI attaches tooltip: "Requires Vector Studio"
- VI connects the signal to a no-op stub

Example pattern:

    actionViewSimilar.setEnabled(false);
    actionViewSimilar.setToolTip("Requires Vector Studio");
    connect(actionViewSimilar, QAction.triggered, this, MainWindow.premiumStub);

`premiumStub()` must do nothing except optionally show a simple "Requires Vector Studio" message.

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

> Detailed conventions (Ruff, error handling, UI patterns, AppState, etc.) are in
> `.github/instructions/coding.instructions.md` which loads automatically for `src/**` files.

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

## 5. TESTING RULES

> Full testing rules are in `.github/instructions/testing.instructions.md` which loads
> automatically for `tests/**` files.

Always run tests using `pdm run pytest`. Do not run tests directly with
`python -m pytest` or the `pytest` CLI without `pdm`.

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
- `views/` -> main screens (e.g., `metadata_view.py`, `visualization_view.py`).
- `components/` -> reusable dialogs and widgets (e.g., `item_details_dialog.py`,
  `loading_dialog.py`).
- Complex views use submodules (e.g., `ui/views/metadata/` for table, threads, I/O, filters).

Service Layer (`src/vector_inspector/services/`):
- Business logic, no Qt dependencies.
- Examples: `visualization_service.py` (DR/clustering),
  `backup_restore_service.py`, `filter_service.py`.

Core Layer (`src/vector_inspector/core/`):
- Provider abstractions and connection management.
- `connections/` -> each provider implements `VectorDBConnection`.
- `connection_manager.py` -> `ConnectionInstance` proxy via `__getattr__`.
- `cache_manager.py` -> caches data by (database, collection) key.

### 6.3 Data Flow Pattern

1. UI view accesses connection via `app_state.provider` (a `ConnectionInstance`).
2. UI view calls connection method (e.g., `app_state.provider.get_all_items()`).
3. `ConnectionInstance.__getattr__` forwards to the provider's `VectorDBConnection`.
4. Service layer processes results (DR, clustering, etc.).
5. Results returned to UI for visualization (Plotly via `QWebEngineView` or matplotlib).

## 7. PROJECT CONVENTIONS

> Detailed conventions (cache, AppState, signals, settings, ThreadedTaskRunner, etc.) are in
> `.github/instructions/coding.instructions.md` which loads automatically for `src/**` files.

### 7.1 Provider Abstraction

- Never call provider SDKs directly in UI or services — always use `ConnectionInstance`.
- Access the connection via `app_state.provider` in UI components.
- All providers implement `VectorDBConnection` (see `core/connections/base_connection.py`).
- `ConnectionInstance.__getattr__` forwards unknown methods to the underlying `database`.
- Example: `app_state.provider.get_all_items()` -> `ChromaDBConnection.get_all_items()`.
- Profile names are injected onto connections: `self.database.profile_name = name`.

## 8. REFERENCES

- `docs/architecture.md` — high-level diagram and rationale.
- `README.md` — install, usage, feature overview.
- `docs/artifact_resolution.md` — LLM-based similarity explanation design.
- `.github/instructions/coding.instructions.md` — full coding conventions for `src/**`.
- `.github/instructions/testing.instructions.md` — full testing rules for `tests/**`.
- `.github/instructions/workflows.instructions.md` — developer workflows and release notes.

## 9. CROSS-REPO NOTE

Vector Studio (the premium extension layer) has its own instructions in
`vector-studio/.github/copilot-instructions.md`. Those rules cover VS-specific extension hooks,
behavior injection, and premium feature patterns only. This file is the authority for
Vector Inspector.
