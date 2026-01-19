# Vector Inspector


A comprehensive desktop application for visualizing, querying, and managing vector database data. Similar to SQL database viewers, Vector Inspector provides an intuitive GUI for exploring vector embeddings, metadata, and performing similarity searches across multiple vector database providers.

## Overview

Vector Inspector bridges the gap between vector databases and user-friendly data exploration tools. While vector databases are powerful for semantic search and AI applications, they often lack the intuitive inspection and management tools that traditional SQL databases have. This project aims to provide that missing layer.

## Key Features

### 1. **Multi-Provider Support**
- Connect to popular vector databases:
  - Pinecone
  - Weaviate
  - Qdrant
  - Milvus
  - ChromaDB
  - FAISS (local files)
  - pgvector (PostgreSQL extension)
  - Elasticsearch with vector search
- Unified interface regardless of backend provider
- Save and manage multiple connection profiles

### 2. **Data Visualization**
- **Metadata Explorer**: Browse and filter vector entries by metadata fields
- **Vector Dimensionality Reduction**: Visualize high-dimensional vectors in 2D/3D using:
  - t-SNE
  - UMAP
  - PCA
- **Cluster Visualization**: Color-code vectors by metadata categories or clustering results
- **Interactive Plots**: Zoom, pan, and select vectors for detailed inspection
- **Data Distribution Charts**: Histograms and statistics for metadata fields

### 3. **Search & Query Interface**
- **Similarity Search**: 
  - Text-to-vector search (with embedding model integration)
  - Vector-to-vector search
  - Find similar items to selected entries
  - Adjustable top-k results and similarity thresholds
- **Metadata Filtering**:
  - SQL-like query builder for metadata
  - Combine vector similarity with metadata filters
  - Advanced filtering: ranges, IN clauses, pattern matching
- **Hybrid Search**: Combine semantic search with keyword search
- **Query History**: Save and reuse frequent queries

### 4. **Data Management**
- **Browse Collections/Indexes**: View all available collections with statistics
- **CRUD Operations**:
  - View individual vectors and their metadata
  - Add new vectors (with auto-embedding options)
  - Update metadata fields
  - Delete vectors (single or batch)
- **Bulk Import/Export**:
  - Import from CSV, JSON, Parquet
  - Export query results to various formats
  - Backup and restore collections
- **Schema Inspector**: View collection configuration, vector dimensions, metadata schema

### 5. **SQL-Like Experience**
- **Query Console**: Write queries in a familiar SQL-like syntax (where supported)
- **Results Grid**: 
  - Sortable, filterable table view
  - Pagination for large result sets
  - Column customization
- **Data Inspector**: Click any row to see full details including raw vector
- **Query Execution Plans**: Understand how queries are executed
- **Auto-completion**: Intelligent suggestions for collection names, fields, and operations

### 6. **Advanced Features**
- **Embedding Model Integration**:
  - Use OpenAI, Cohere, HuggingFace models for text-to-vector conversion
  - Local model support (sentence-transformers)
  - Custom model integration
- **Vector Analysis**:
  - Compute similarity matrices
  - Identify outliers and anomalies
  - Cluster analysis with k-means, DBSCAN
- **Embedding Inspector**:
  - For similar collections or items, automatically identify which vector dimensions (activations) most contribute to the similarity
  - Map key activations to interpretable concepts (e.g., 'humor', 'sadness', 'anger') using metadata or labels
  - Generate human-readable explanations for why items are similar
- **Performance Monitoring**:
  - Query latency tracking
  - Index performance metrics
  - Connection health monitoring

## Architecture

### Technology Stack

#### Frontend (GUI)
- **Framework**: PySide6 (Qt for Python) - native desktop application
- **UI Components**: Qt Widgets for forms, dialogs, and application structure
- **Visualization**: 
  - Plotly for interactive charts (embedded via QWebEngineView)
  - matplotlib for static visualizations
- **Data Grid**: QTableView with custom models for high-performance data display

#### Backend
- **Language**: Python 3.9+
- **Core Libraries**:
  - Vector DB clients: `pinecone-client`, `weaviate-client`, `qdrant-client`, `pymilvus`, `chromadb`, etc.
  - Embeddings: `sentence-transformers`, `openai`, `cohere`
  - Data processing: `pandas`, `numpy`
  - Dimensionality reduction: `scikit-learn`, `umap-learn`
- **API Layer**: FastAPI (if separating frontend/backend) or direct Python integration

#### Data Layer
- **Connection Management**: SQLAlchemy-style connection pooling adapted for vector DBs
- **Query Abstraction**: Unified query interface that translates to provider-specific syntax
- **Storage Modes**:
  - Qdrant Remote: connect via host/port (e.g., localhost:6333)
  - Qdrant Embedded: `QdrantClient(path="./data/qdrant_local")` to persist locally without a separate server
- **Caching**: Redis or in-memory cache for frequently accessed data

### Application Structure

```
vector-inspector/
├── src/
│   ├── core/
│   │   ├── connections/       # Connection managers for each provider
│   │   ├── query/             # Query abstraction layer
│   │   └── models/            # Data models
│   ├── ui/
│   │   ├── components/        # Reusable UI components
│   │   ├── views/             # Main application views
│   │   └── styles/            # Styling
│   ├── services/
│   │   ├── embedding/         # Embedding model integrations
│   │   ├── visualization/     # Viz engine
│   │   └── export/            # Import/export handlers
│   └── utils/
├── tests/
├── docs/
├── config/
│   └── connections.json       # Saved connection profiles
└── pyproject.toml
```

## Use Cases

1. **AI/ML Development**: Inspect embeddings generated during model development
2. **RAG System Debugging**: Verify what documents are being retrieved
3. **Data Quality Assurance**: Identify poorly embedded or outlier vectors
4. **Production Monitoring**: Check vector database health and data consistency
5. **Data Migration**: Transfer data between vector database providers
6. **Education**: Learn and experiment with vector databases interactively

## Feature Access (Free vs Pro)

| Feature                                      | Access   |
|----------------------------------------------|----------|
| Connection to ChromaDB                       | Free     |
| Basic metadata browsing and filtering        | Free     |
| Simple similarity search interface           | Free     |
| 2D vector visualization (PCA/t-SNE)          | Free     |
| Basic CRUD operations                        | Free     |
| Metadata filtering (advanced)                | Free     |
| Item editing                                 | Free     |
| Import/export (CSV, JSON, Parquet)           | Free     |
| Provider abstraction layer                   | Free     |
| Pinecone support                             | Free     |
| Weaviate support                             | Free     |
| Qdrant support                               | Pro      |
| Milvus support                               | Pro      |
| ChromaDB advanced support                    | Pro      |
| FAISS (local files) support                  | Pro      |
| pgvector (PostgreSQL extension) support      | Pro      |
| Elasticsearch with vector search support     | Pro      |
| Advanced query builder                       | Free     |
| 3D visualization                             | Free     |
| Embedding model integration (basic)          | Free     |
| Query history and saved queries              | Free     |
| Model Comparison Mode                        | Pro      |
| Cluster Explorer                             | Pro      |
| Embedding Inspector                          | Pro      |
| Embedding Provenance Graph                   | Pro      |
| Semantic Drift Timeline                      | Pro      |
| Cross-Collection Similarity                  | Pro      |
| Vector Surgery                               | Pro      |
| Custom plugin system                         | Pro      |
| Team collaboration features                  | Pro      |

## Planned Roadmap

### Phase 1: Foundation (MVP)
- [x] Connection to ChromaDB
- [x] Basic metadata browsing and filtering
- [x] Simple similarity search interface
- [x] 2D vector visualization (PCA/t-SNE)
- [x] Basic CRUD operations

### Phase 2: Core Features
- [x] Metadata filtering (advanced filtering, combine with search)
- [x] Item editing (update metadata and documents)
- [x] Import/export (CSV, JSON, Parquet, backup/restore)
- [x] Provider abstraction layer (unified interface for all supported vector DBs)

### Phase 3: UX & Professional Polish
- [ ] **Unified Information Panel** (new "Info" tab as default view)
- [ ] Database and collection metadata display
- [ ] Connection health and version information
- [ ] Schema visualization and index configuration display

### Phase 4: Modular/Plugin System & Hybrid Model
- [ ] Implement modular/plugin system for feature extensions
- [ ] Migrate paid/advanced features to commercial modules
- [ ] Add licensing/access control for commercial features

### Phase 5: Provider Expansion (Incremental)
- [ ] Pinecone support (free)
- [ ] Weaviate support (free)
- [ ] Qdrant support (paid)

#### Future/Backlog Providers
- [ ] Milvus support (paid)
- [ ] ChromaDB advanced support (paid)
- [ ] FAISS (local files) support (paid)
- [ ] pgvector (PostgreSQL extension) support (paid)
- [ ] Elasticsearch with vector search support (paid)


### Phase 6A: Advanced Usability & Visualization
- [ ] Advanced query builder (free)
- [ ] 3D visualization (free)
- [ ] Embedding model integration (free)
- [ ] Query history and saved queries (free)
- [ ] Metadata Type Detection & Rich Media Preview (free)

### Phase 6B: Analytical & Comparison Tools
- [ ] Model Comparison Mode (paid)
- [ ] Cluster Explorer (paid)
- [ ] Embedding Inspector (paid)
- [ ] Embedding Provenance Graph (paid)

### Phase 6C: Temporal & Cross-Collection Analytics
- [ ] Semantic Drift Timeline (paid)
- [ ] Cross-Collection Similarity (paid)

### Phase 6D: Experimental & Power Features
- [ ] Vector Surgery (paid)
- [ ] Custom plugin system (paid)
- [ ] Team collaboration features (paid)

### Phase 7: Enterprise Features
- [ ] Multi-user support with auth
- [ ] Audit logging
- [ ] Advanced security features
- [ ] Custom reporting
- [ ] API for programmatic access

## Installation (Planned)

```bash
# Install from PyPI
pipx install vector-inspector

# Or run from source
git clone https://github.com/yourusername/vector-inspector.git
cd vector-inspector
pdm install

# Launch application
pdm run vector-inspector
```

## Configuration

Paths are resolved relative to the project root (where `pyproject.toml` is). For example, entering `./data/chrome_db` will use the absolute path resolved from the project root.

Connections can be saved (planned) in `~/.vector-inspector/connections.json`:

```json
{
  "connections": [
    {
      "name": "Production Pinecone",
      "provider": "pinecone",
      "api_key": "...",
      "environment": "us-west1-gcp",
      "index": "my-index"
    },
    {
      "name": "Local ChromaDB",
      "provider": "chromadb",
      "path": "/path/to/chroma/data"
    }
  ]
}
```

## Development Setup

```bash
# Install PDM if you haven't already
pip install pdm

# Install dependencies (PDM will create venv automatically)
pdm install

# Install with development dependencies
pdm install -d

# Run tests
pdm run pytest

# Run application in development mode
pdm run vector-inspector
```

## Contributing

Contributions are welcome! Areas where help is needed:
- Additional vector database provider integrations
- UI/UX improvements
- Performance optimizations
- Documentation
- Test coverage

Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## License

MIT License - See [LICENSE](LICENSE) file for details.

## Acknowledgments

This project draws inspiration from:
- DBeaver (SQL database viewer)
- MongoDB Compass (NoSQL database GUI)
- Pinecone Console
- Various vector database management tools

---

**Status**: ✅ Phase 2 Complete - Advanced Features Implemented!

**What's New in Phase 2:**
- 🔍 Advanced metadata filtering with customizable filter rules (AND/OR logic)
- ✏️ Double-click to edit items directly in the data browser
- 📥 Import data from CSV, JSON, and Parquet files
- 📤 Export filtered data to CSV, JSON, and Parquet formats
- 💾 Comprehensive backup and restore system for collections
- 🔄 Metadata filters integrated with search for powerful queries

See [GETTING_STARTED.md](GETTING_STARTED.md) for usage instructions and [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details.

**Contact**: Anthony Dawson
