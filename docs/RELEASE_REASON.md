## Release Notes (0.5.4) — 2026-03-02

### Bug Fixes
- Fix WebEngine shutdown warnings: ensure QWebEnginePage/QWebEngineView and QWebChannel are explicitly disposed before application shutdown to avoid "Release of profile requested but WebEnginePage still not deleted" warnings in CI and on user machines. Files updated: `src/vector_inspector/ui/views/visualization/plot_panel.py`, `src/vector_inspector/ui/views/visualization/histogram_panel.py`, `src/vector_inspector/ui/views/visualization_view.py`, `src/vector_inspector/ui/main_window.py`.

- Fix histogram scan bug: when scanning other connections for collections with the same embedding dimensionality, avoid excluding collections from other connections that happen to share the same collection name as the primary collection. The background scanner now only excludes the primary collection on the same connection. File updated: `src/vector_inspector/ui/views/visualization/histogram_panel.py`.

---