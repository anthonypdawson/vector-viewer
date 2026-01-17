# Core vs Pro Architecture Plan

This document outlines the architectural approach for separating core and pro features in the Vector Viewer application.

## Overview

- **Core**: Contains all base functionality. It is feature-agnostic regarding Pro and exposes extension points (hooks) for UI and logic.
- **Pro**: Contains only Pro-level features. It depends on Core and uses Core's hooks to extend or enhance the application.

## Principles

- **Separation of Concerns**: Core does not reference or know about Pro features. Pro depends on Core, not the other way around.
- **Extensibility**: Core provides hooks (e.g., to add tabs, extend forms, or update logic) so new features can be added without modifying core code.
- **Modularity**: Both Core and Pro can be bundled, installed, and run as separate packages.
- **No Plugin System Required (Initially)**: A full plugin system is not needed at first. Hooks and extension points are sufficient. Migration to a plugin system can be considered in the future.

## Implementation Guidelines

- **Core**
  - Expose hooks for UI and logic extension (e.g., signals, callback registration, or extension classes).
  - Do not import or reference Pro code.
  - Document extension points clearly for use by Pro or other future extensions.

- **Pro**
  - Import and depend on Core.
  - Use Core's hooks to add or modify UI and logic.
  - Contain only Pro-specific code and features.

## Example Use Cases

- Adding a new tab in the UI: Core exposes a hook for tab registration. Pro registers its tab via this hook.
- Extending a form: Core provides a way to inject new fields. Pro uses this to add Pro-only options.
- Upgrading functionality: Pro can override or extend Core logic using provided extension points.

## Benefits

- Clean separation between open and paid features.
- Easier maintenance and testing.
- Flexibility to add/remove Pro features without touching Core.
- Foundation for a future plugin system if needed.

---

This approach is widely used in open-core software and provides a robust, maintainable path for future growth.
