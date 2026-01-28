# Latest updates

- Major refactor and studio-ready architecture
  - Refactored main window into modular components (InspectorShell, ProviderFactory, DialogService, ConnectionController, InspectorTabs)
  - MainWindow is reusable as a widget; tab system is pluggable so Studio can extend or override tabs

- Data browser improvements
  - Added Generate embeddings on edit (persisted per user)

- Settings / Preferences
  - SettingsService persists preferences and exposes typed accessors (breadcrumb, search defaults, auto-embed, window geometry)
  - SettingsService emits a setting_changed Qt signal so UI reacts immediately
  - SettingsDialog (modal) added with add_section API and hook integration for extension panels
  - Breadcrumb controls moved out of core so Pro (Vector Studio) injects them via the settings_panel_hook

- Extension hook for settings panels
  - *settings_panel_hook* added to *vector_inspector.extensions*; Vector Studio registers breadcrumb controls at startup

- Breadcrumb and UI improvements
  - Breadcrumb label now elides long trails (left/middle) and shows full trail on hover
  - SearchView supports runtime elide-mode changes and responds to settings signals

- Window geometry persistence
  - Main window saves/restores geometry when window.restore_geometry is enabled

- Pro (Vector Studio) features
  - *Search Similar* (Pro): right-click any row in Data Browser or Search Results to run a vector-to-vector similarity search
  - *table_context_menu* handler hardened for many embedding/id formats and includes fallbacks
  - Vector Studio injects breadcrumb controls into Settings dialog via *settings_panel_hook*

- Tests and CI
  - Added *tests/test_settings_injection.py* to assert settings panel hook registration
  - Updated context-menu tests to use *log_info* and *assert* for pytest
  - Local test run: 5 tests passed; GUI-heavy suite ~9s due to PySide6 startup

---