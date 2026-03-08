## Release Notes (0.6.0) — 2026-03-02

### LLM Provider Layer
- Add pluggable `LLMProvider` abstraction (`core/llm_providers/`) with three implementations: `LlamaCppProvider` (in-process, zero-setup default), `OllamaProvider` (used opportunistically when Ollama is running locally), and `OpenAICompatibleProvider` (cloud or local OpenAI-compatible APIs).
- Add `LLMProviderFactory` with auto-detection: user-configured → Ollama (probed at `localhost:11434`) → llama-cpp fallback.
- Add `LLMProviderInstance` runtime wrapper on `AppState` (`app_state.llm_provider`) for lazy initialisation and `refresh()` after settings changes.
- Default llama-cpp model: Phi-3-mini-4k-instruct Q4_K_M (~2.4 GB); `download_default_model()` helper downloads on first use with progress callback support.
- New optional dependency group `llm` (`llama-cpp-python>=0.3.0`); install with `pdm add "vector-inspector[llm]"`.

- Developer: add hidden CLI flag `--llm-console` to open an interactive LLM test window alongside the main app for manual provider testing and quick reloads.

### Settings
- Add LLM provider settings keys to `SettingsService` (`llm.provider`, `llm.model_path`, `llm.cache_dir`, `llm.ollama_url`, `llm.ollama_model`, `llm.openai_url`, `llm.openai_api_key`, `llm.openai_model`, `llm.context_length`, `llm.temperature`) with typed getters/setters.
- Add **LLM Provider** status group to the Settings dialog (free tier): shows configured provider, live availability check button, and a disabled "Configure LLM…" stub that Vector Studio enables.
- Vector Studio: add full **LLM Configuration** settings panel (provider dropdown, model browser, download button, Ollama/OpenAI-compatible fields, context length, temperature) injected via `settings_panel_hook`.
  
	Note: For ease of local verification and testing, this PR temporarily includes the full LLM configuration panel directly in Vector Inspector (see `src/vector_inspector/extensions/llm_settings_panel.py`). The long-term plan is for Vector Studio to inject the full configuration UI via `settings_panel_hook` while the free tier in Vector Inspector exposes only the small status group and a disabled "Configure LLM…" stub. This placement is intentional for developer testing and will be migrated to the Vector Studio extension in a follow-up change.

### Testing
- Add 22 unit tests in `tests/core/llm_providers/` covering factory provider selection, auto-detection order and fallback, provider availability mocking, `generate()` response parsing, and `LLMProviderInstance` refresh behaviour.
- Add comprehensive LLM provider contract tests: streaming paths, error/exception handling, `get_model_name`, `is_available` HTTP probe, llama-cpp cache helpers (`get_llm_cache_dir`, `list_cached_models`, `download_default_model`), `get_capabilities`, and `get_health` for all three providers. Core LLM provider coverage raised from 78% to 95%.
- Add `tests/ui/test_llm_settings_panel.py` (item 15): widget structure checks, provider switching, API key `maximumWidth`/full-value-storage assertion, and thread unit tests (`_HealthCheckThread`, `_ModelListThread`) called synchronously without a Qt event loop.
- Add 17 `SettingsService` getter/setter unit tests covering all LLM settings keys.
- Fix `datetime.UTC` (Python 3.11+ only) → `datetime.timezone.utc` in `base_provider.py`, `ollama_provider.py`, `openai_compatible_provider.py`, `runtime_manager.py`, and `llm_settings_panel.py`.

### Bug Fixes
- Fix WebEngine shutdown warnings: ensure QWebEnginePage/QWebEngineView and QWebChannel are explicitly disposed before application shutdown to avoid "Release of profile requested but WebEnginePage still not deleted" warnings in CI and on user machines. Files updated: `src/vector_inspector/ui/views/visualization/plot_panel.py`, `src/vector_inspector/ui/views/visualization/histogram_panel.py`, `src/vector_inspector/ui/views/visualization_view.py`, `src/vector_inspector/ui/main_window.py`.

- Fix histogram scan bug: when scanning other connections for collections with the same embedding dimensionality, avoid excluding collections from other connections that happen to share the same collection name as the primary collection. The background scanner now only excludes the primary collection on the same connection. File updated: `src/vector_inspector/ui/views/visualization/histogram_panel.py`.

---