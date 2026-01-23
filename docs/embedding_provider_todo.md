# Embedding Provider: Implementation TODO

Purpose: Introduce a pluggable `EmbeddingProvider` system that allows users to select or register embedding models (text, image, multimodal). The system will handle detection, lazy loading, metadata extraction, normalization, and per-collection persistence.

Priority: High

Planned steps

1. Design `EmbeddingProvider` interface
   - Methods: `get_metadata()`, `encode(inputs)`, `warmup()`, `close()`
   - Metadata fields: `name`, `version`, `dimension`, `modality` (text/image/multimodal), `normalization` (none/l2), `source` (hf/local/custom)

2. Implement loaders (lazy-load) for common model families
   - `SentenceTransformerProvider` (sentence-transformers)
   - `CLIPProvider` (transformers CLIPModel + processor)
   - Generic `HFProvider` that inspects model config for embed dim

3. Model registry / known models
   - Move hardcoded `DIMENSION_TO_MODEL` into a registry file under `docs/` or `src/` (start in `docs/known_embedding_models.md`)
   - Provide CLI / UI to extend registry

4. Settings persistence
   - Add per-collection chosen provider to `SettingsService` (keyed by `connection_id:collection`)
   - Add migration logic to handle missing/invalid providers

5. UI
   - Dialog to choose provider for a collection (auto-detect, built-in, custom model name/path)
   - Show detected metadata (dim, modality) and a validation button
   - Show loading progress when fetching/initializing large models

6. Validation and safety
   - If provider.dim != collection.dim: warn and offer to skip or reindex
   - Cache embeddings and model instances; provide a clear-cache action

7. Tests and docs
   - Unit tests for loaders and metadata detection
   - Document the JSON/YAML registry format and how to add custom models

Notes / Implementation considerations

- Lazy-loading is critical to avoid UI freezes; load models on-demand and provide progress UI.
- Normalize outputs consistently (e.g. L2) based on provider metadata.
- Securely store credentials for remote models (if used) with `CredentialService`.
- Start with the small set of tested models, expand registry as we discover more.

---

If you want I can scaffold the `EmbeddingProvider` Python interface and one example provider next.
