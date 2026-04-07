---
applyTo: "**"
---

# Developer Workflows & Release Notes

## Install & Run

```
pip install pdm
pdm install -d
pdm run python -m vector_inspector

./scripts/run.sh      # Linux/macOS
./scripts/run.bat     # Windows
```

## Build & Release

- PyPI upload: `./pypi-upload.sh` (requires `~/.pypirc`).
- Versioning: managed by `bumpver` (see `bumpver.toml`).
- CI/CD: GitHub Actions in `.github/workflows/`:
  - `ci-tests.yml` -> tests on push/PR.
  - `release-and-publish.yml` -> publishes to PyPI on tags.
  - `nuitka.yml` -> experimental native compilation.

## Managing Dependencies (PDM)

- Add a runtime dependency: `pdm add <package>`
- Add a dev/test-only dependency: `pdm add -d <package>`
- Heavy or optional dependencies (e.g. `sklearn`, `umap-learn`, `hdbscan`, `plotly`) **must** be added
  via `utils/lazy_imports.py` rather than a top-level import, so startup time is not affected and the
  app degrades gracefully when they are absent.
- After editing `pyproject.toml` manually, run `pdm install` to sync the lock file.
- Never `pip install` into the project's venv directly — always use `pdm add` so the lock file stays current.

## Release Notes

All release notes are added in `docs/RELEASE_REASON.md`, not in this file.
This file is cleared when the version is incremented and a new release is created.

**Format:**

```markdown
# Release Notes (0.x.y) — YYYY-MM-DD
Short introductory paragraph summarizing the release highlights and new capabilities.
## Section heading
- Individual change
- Individual change

## Another section (omit if empty)
### Subsection (optional)
- Individual change

---
```

- The heading uses the *next* version number and today's date (update the date whenever new entries are added).
- Format of each heading does not have to be exact to the example, but should be consistent and parseable by the release workflow.
- Group changes under short section headings (e.g. `## UI`, `## Providers`, `## Testing`, `## Bug Fixes`). Omit a section if it has no entries.
- Each bullet is one user-visible or developer-visible change, written in plain language.
- The file ends with a horizontal rule `---` on its own line.
- When a release is cut, this file is cleared and a fresh heading for the next version is started.
- **When to add an entry:** Any change substantial enough to matter to a user or developer should be
  recorded — new features, changed behavior, bug fixes, provider additions, UI changes, breaking changes,
  and significant internal improvements (e.g., new test infrastructure or CI changes). Skip trivial
  refactors, whitespace fixes, and internal rename-only changes that have no visible effect.
