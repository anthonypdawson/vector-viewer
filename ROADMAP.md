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

## Phase 3: UX & Professional Polish
- [ ] **Unified Information Panel** (new "Info" tab as default view)
- [ ] Database and collection metadata display
- [ ] Connection health and version information
- [ ] Schema visualization and index configuration display

## Phase 4: Modular/Plugin System & Hybrid Model
- [ ] Implement modular/plugin system for feature extensions
- [ ] Migrate paid/advanced features to commercial modules
- [ ] Add licensing/access control for commercial features

## Phase 5: Provider Expansion (Incremental)
- [ ] Pinecone support (free)
- [ ] Weaviate support (free)
- [ ] Qdrant support (paid)

### Future/Backlog Providers
- [ ] Milvus support (paid)
- [ ] ChromaDB advanced support (paid)
- [ ] FAISS (local files) support (paid)
- [ ] pgvector (PostgreSQL extension) support (paid)
- [ ] Elasticsearch with vector search support (paid)

## Phase 6A: Advanced Usability & Visualization
- [ ] Advanced query builder (free)
- [ ] 3D visualization (free)
- [ ] Embedding model integration (free)
- [ ] Query history and saved queries (free)
- [ ] Metadata Type Detection & Rich Media Preview (free)

## Phase 6B: Analytical & Comparison Tools
- [ ] Model Comparison Mode (paid)
- [ ] Cluster Explorer (paid)
- [ ] Embedding Inspector (paid)
- [ ] Embedding Provenance Graph (paid)

## Phase 6C: Temporal & Cross-Collection Analytics
- [ ] Semantic Drift Timeline (paid)
- [ ] Cross-Collection Similarity (paid)

## Phase 6D: Experimental & Power Features
- [ ] Vector Surgery (paid)
- [ ] Custom plugin system (paid)
- [ ] Team collaboration features (paid)

## Phase 7: Enterprise Features
- [ ] Multi-user support with auth
- [ ] Audit logging
- [ ] Advanced security features
- [ ] Custom reporting
- [ ] API for programmatic access (FastAPI backend)
- [ ] Caching layer (Redis/in-memory) for performance
- [ ] Connection pooling and optimization
