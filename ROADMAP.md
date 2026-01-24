# Vector Inspector Roadmap

## Phase 1: Foundation (MVP)
- [x] Connection to ChromaDB
- [x] Basic metadata browsing and filtering
- [x] Simple similarity search interface
- [x] 2D vector visualization (PCA/t-SNE)
- [x] Basic CRUD operations

## Phase 2: Core Features
- [x] Metadata filtering (advanced filtering, combine with search)
- [x] Item editing (update metadata and documents)
- [x] Import/export (CSV, JSON, Parquet, backup/restore)
- [x] Provider abstraction layer (unified interface for all supported vector DBs)
- [x] Qdrant support (basic/experimental, free)

## Phase 3: Pinecone Support (HIGH PRIORITY)
- [x] Pinecone support (core embedding logic, provider abstraction, UI integration)
- [x] Cross-database migration (dedicated controls for migrating collections between providers)
  
**Phase 3 Status:**
All core features for Pinecone support are now implemented and tested. Embedding logic is standardized across providers, and the embedding model registry has been moved to `config/known_embedding_models.json` for maintainability. Documentation and UI have been updated to reflect these changes. Transitioning to Phase 4 and advanced analytics features.


## Phase 4: Provider Expansion (HIGH PRIORITY)
- [ ] Weaviate support
- [ ] Milvus support
- [ ] FAISS (local files) support
- [ ] pgvector (PostgreSQL extension) support
- [ ] Elasticsearch with vector search support

 > **Priority:** Reach 5-6 database providers quickly to market as "most comprehensive vector DB tool." All providers remain free.
 
---
**Recent Work Completed:**
- Standardized provider output (distance metric)
- Centralized embedding logic
- Moved embedding model registry to config/
- Updated documentation and UI for model selection
- Improved loading dialogs and UX for slow actions
- Refactored PineconeConnection for consistency
- Updated docs for completed features and current phase

## Phase 5: Analytical & Comparison Tools (DIFFERENTIATOR)
- [ ] **Embedding Inspector** (free) - **PRIORITY: Killer differentiator feature**
- [ ] Model Comparison Mode (free)
- [ ] Cluster Explorer (free)
- [ ] Embedding Provenance Graph (free)

> **Priority:** Ship analytics early to differentiate from competitors. Embedding Inspector is the standout feature. All free until paid platform infrastructure is ready.

## Phase 6: UX & Professional Polish
- [x] **Unified Information Panel** (new "Info" tab as default view)
- [x] Database and collection metadata display
- [ ] Connection health and version information
- [ ] Schema visualization and index configuration display

## Phase 7: Modular/Plugin System & Hybrid Model
- [ ] Implement modular/plugin system for feature extensions
- [ ] Migrate paid/advanced features to commercial modules
- [ ] Add licensing/access control for commercial features

## Phase 8: Advanced Usability & Visualization
- [ ] Advanced query builder (free)
- [ ] 3D visualization (free)
- [ ] Embedding model integration (basic, free)
- [ ] Query history (recent queries, free)
- [ ] Saved queries (named, persistent, Pro)
- [ ] Metadata Type Detection & Rich Media Preview (free)

## Phase 9: Temporal & Cross-Collection Analytics
- [ ] Semantic Drift Timeline (paid)
- [ ] Cross-Collection Similarity (paid)

## Phase 10: Experimental & Power Features
- [ ] Vector Surgery (Pro)
- [ ] Custom plugin system (Pro)
- [ ] Team collaboration features (Pro)
- [ ] Parquet import/export (Pro)
- [ ] Bulk import/export pipelines (Pro)
- [ ] Advanced embedding workflows (Pro)
  - Large batch processing
  - Multiple model selection
  - GPU acceleration
- [ ] Advanced provider features (Pro)
  - Cloud authentication flows
  - Hybrid search
  - Performance profiling
  - Index optimization tools

## Phase 11: Enterprise Features (Pro)
- [ ] Multi-user support with auth
- [ ] Audit logging
- [ ] Advanced security features
- [ ] Custom reporting and dashboards
- [ ] API for programmatic access (FastAPI backend)
- [ ] Cross-collection queries and analytics
- [ ] Team workspaces and sharing

> **Enterprise features enhance collaboration and scale.** All core functionality remains free.
