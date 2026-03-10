---
applyTo: "tests/**"
---

# Testing Rules (Pytest + Qt)

These rules apply when working in the `tests/` directory.

## Running Tests

```
pdm run pytest --cov=vector_inspector --cov-report=html
pdm run pytest tests/test_metadata_navigation.py
pdm run pytest -n auto
QT_QPA_PLATFORM=offscreen pdm run pytest
```

Always run tests using `pdm run pytest`. Do not run tests directly with
`python -m pytest` or the `pytest` CLI without `pdm` — the project relies on
the `pdm` environment and dependency isolation to produce consistent test
results across developer machines and CI.

- Tests use `pytest` with `pytest-qt` for Qt widget testing.
- `tests/conftest.py` provides `fake_provider` fixture — a mock vector DB for isolated testing.
- To get the report of which files need coverage you can use the command line
    `pdm run pytest -q --cov=vector_inspector --cov-report term-missing`

**Coverage target:** Aim for 80% on new code. This is a guideline, not an absolute requirement — if a code path is only reachable through excessive mocking or is genuinely impractical to test (e.g., OS-specific crash handlers), skip it and leave a comment explaining why. Do not over-engineer test fixtures or add fragile tests just to hit the number.
 - For non-UI code, prefer pure unit tests with mocks/fakes to keep them fast and deterministic. Aim for 100% coverage on critical logic (e.g., provider interactions, data transformations) and at least 80% on new code paths. Prefer 90% avg
 - For UI code, use `pytest-qt` to test signal emissions, widget state changes, and user interactions. Focus on testing the glue logic and critical paths; it's acceptable to have lower coverage on complex UI layouts or third-party widget behavior. Use fixtures to set up common UI states and interactions. Prefer 80%+ coverage on new UI components and interactions, but prioritize meaningful tests over arbitrary numbers.

## Organization

- Tests should be organized by feature, not by type.
  - Good: `test_plot_selection.py` contains all plot selection tests (with and without Qt).
  - Bad: separate `test_plot_selection_qt.py` and `test_plot_selection_unit.py`.

## Qt & Providers

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

**Shared fixtures in `tests/conftest.py`** — always prefer these over duplicating setup in individual test files:

| Fixture | Type | Description |
|---|---|---|
| `fake_provider` | `FakeProvider` | Pre-populated with `test_collection` (ids `id1`/`id2`/`id3`, embeddings `[1,0]`/`[0,1]`/`[0.5,0.5]`). Use for most provider-dependent tests. |
| `empty_fake_provider` | `FakeProvider` | Empty provider with no collections. Use for "no data" and first-create scenarios. |
| `fake_provider_with_name` | `tuple[FakeProvider, str]` | Returns `(provider, "test_collection")`. Use when the collection name is needed as a variable. |
| `app_state_with_fake_provider` | `AppState` | `AppState` with `fake_provider` already set as `provider`. Use for full-stack view tests. |
| `task_runner` | `ThreadedTaskRunner` | Fresh `ThreadedTaskRunner` instance. Pass alongside `app_state` when constructing views. |
| `fake_settings` | `FakeSettings` | Minimal settings stub; suppresses the splash dialog and exposes `get`/`set_use_accent_enabled`. Use for settings-dependent component tests. |

**Fixture ownership:** If you create a new fixture that is broadly useful (more than one test file would benefit from it), or you discover a fixture defined in a test file that logically belongs in `conftest.py`, move it there. Keep `conftest.py` as the single source of truth for shared test infrastructure.

## Unit Test Directory Structure

- Organize tests by *feature area* (views, components, providers, services, metadata), not by test type.
- Recommended top-level layout:
  - `tests/components/` — small widget and component tests (QWidgets, dialogs).
  - `tests/views/` — full view integration tests that exercise multiple components.
  - `tests/providers/` — provider implementations and DB adapter tests (Chroma, Pinecone, Qdrant, etc.).
  - `tests/services/` — business-logic/service-level unit tests (visualization, backup, cache).
  - `tests/metadata/` — metadata-specific helpers and features.
  - `tests/fakes/` or `tests/fixtures/` — shared fake providers, common test data, utility fixtures.

- File naming and scope:
  - Name files by feature: `test_profile_manager_panel.py`, `test_connection_view.py`.
  - Keep tests small and focused; prefer multiple small test files over one large file per feature.

- Qt testing tips:
  - Use `qtbot` for any test interacting with Qt widgets or signals.
  - Stub blocking native dialogs (`QMessageBox`, `QFileDialog`, `QInputDialog`, `QProgressDialog`) in `tests/conftest.py` when possible.
  - Replace or run QThread-based workers synchronously in tests to avoid race conditions.

- Provider tests:
  - Inject fake provider clients via fixtures or `sys.modules` to avoid heavy third-party SDK imports.
  - Mock external SDK symbols (e.g., `pinecone.Pinecone`) rather than relying on module-level attributes to make tests robust to import order.

- Running tests:
  - Always run via `pdm run pytest` to ensure the correct environment.
  - Use `QT_QPA_PLATFORM=offscreen` in CI for headless runs.

## Required Tests for New Functionality

- Any new functionality, public API, UI surface, or code path added to the project MUST include unit tests that exercise the behavior.
- Tests for UI-related changes must use `qtbot` where appropriate (see Qt & Providers above).
- Place new tests under the appropriate `tests/` feature directory following the existing conventions (components, views, services, providers, etc.).
- Tests should be small, focused, and deterministic; prefer fixtures (e.g., `fake_provider`) and mocks to avoid external dependencies.
- When adding behavior that affects multiple layers (UI + service), include both a unit test for the service logic and a lightweight widget test for the UI glue where practical.
- Add tests that cover edge cases and error paths for any new code paths to prevent regressions.
- If a change is exploratory or a spike, include at least one regression test capturing the expected outcome before landing the change.
- Always reuse or extend existing fixtures and test utilities where possible to maintain consistency and reduce boilerplate in tests.
- Always use the same test files and organization patterns as existing tests for the relevant feature area to keep the test suite coherent and navigable.
- **Do not leave source-file line numbers in test comments, docstrings, or section headers** (e.g. `# line 123`, `"""Lines 45-67: ..."""`, `(lines 100-110)`). They are acceptable as a temporary aid while actively writing coverage tests, but must be removed before the work is considered done. Line numbers change whenever the source is modified, making stale references misleading and noisy. Describe *what* the test exercises, not *where* in the file it lives.
