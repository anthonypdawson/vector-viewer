# Vector Viewer

A comprehensive desktop application for visualizing, querying, and managing vector database data. Similar to SQL database viewers, Vector Viewer provides an intuitive GUI for exploring vector embeddings, metadata, and performing similarity searches across multiple vector database providers.

## Overview

Vector Viewer bridges the gap between vector databases and user-friendly data exploration tools. While vector databases are powerful for semantic search and AI applications, they often lack the intuitive inspection and management tools that traditional SQL databases have. This project aims to provide that missing layer.

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
- **Caching**: Redis or in-memory cache for frequently accessed data

### Application Structure

```
vector-viewer/
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

## Planned Roadmap

### Phase 1: Foundation (MVP)
- [x] Connection to ChromaDB
- [x] Basic metadata browsing and filtering
- [x] Simple similarity search interface
- [x] 2D vector visualization (PCA/t-SNE)
- [x] Basic CRUD operations

### Phase 2: Core Features
- [ ] Support for all major providers
- [ ] Advanced query builder
- [ ] 3D visualization
- [ ] Embedding model integration
- [ ] Import/export functionality
- [ ] Query history and saved queries

### Phase 3: Advanced Features
- [ ] Cluster analysis tools
- [ ] Performance monitoring
- [ ] Bulk operations
- [ ] Embedding Inspector (explain why items/collections are similar, with interpretable activations)
- [ ] Custom plugin system
- [ ] Team collaboration features (shared queries, annotations)

### Phase 4: Enterprise Features
- [ ] Multi-user support with auth
- [ ] Audit logging
- [ ] Advanced security features
- [ ] Custom reporting
- [ ] API for programmatic access

## Installation (Planned)

```bash
# Install from PyPI
pipx install vector-viewer

# Or run from source
git clone https://github.com/yourusername/vector-viewer.git
cd vector-viewer
pdm install

# Launch application
pdm run vector-viewer
```

## Configuration

Paths are resolved relative to the project root (where `pyproject.toml` is). For example, entering `./data/chrome_db` will use the absolute path resolved from the project root.

Connections can be saved (planned) in `~/.vector-viewer/connections.json`:

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
pdm run vector-viewer
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

**Status**: ✅ Phase 1 Complete - Ready for Testing!

See [GETTING_STARTED.md](GETTING_STARTED.md) for usage instructions and [IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md) for technical details.

**Contact**: Anthony Dawson
