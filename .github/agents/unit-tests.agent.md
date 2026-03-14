---
name: Unit Tests & Coverage Assistant
description: >
  This agent specializes in unit tests and coverage for the `vector-inspector` repo.
  Use it to write or fix pytest tests, run targeted test runs, diagnose failures,
  and suggest minimal code changes to improve testability and coverage.

  Quick commands:
  - Show tests: `pdm run pytest -q`
  - Run single test file: `pdm run pytest tests/path/to/test_file.py -q`
  - Run single test: `pdm run pytest tests/path/to/test_file.py::test_name -q`
  - Coverage (local): `pdm run coverage run -m pytest && pdm run coverage html`

  Examples:
  - Run failing tests in `tests/views/test_search_view.py` and suggest a fix.
  - Add tests for `services/visualization_service.py` to cover edge cases.
  - Reduce a flaky test by isolating external state and mocking the provider.

target: github-copilot
tools:
  - apply_patch
  - read_file
  - file_search
  - grep_search
  - run_in_terminal
  - manage_todo_list
github:
  permissions:
    contents: write
    pull-requests: read
---

Quick prompts to try:

- "Use the Unit Tests & Coverage Assistant to run tests and fix failures."
- "Write a pytest for `src/vector_inspector/services/visualization_service.py` that covers the PCA branch."
- "Run coverage and give a short plan to raise coverage to 85% for `src/vector_inspector/services/`"

