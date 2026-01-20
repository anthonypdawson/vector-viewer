# Vector Inspector


A comprehensive desktop application for visualizing, querying, and managing vector database data. Similar to SQL database viewers, Vector Inspector provides an intuitive GUI for exploring vector embeddings, metadata, and performing similarity searches across multiple vector database providers.

## Overview

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Application Structure](#application-structure)
- [Use Cases](#use-cases)
- [Feature Access](#feature-access)
- [Roadmap](#roadmap)
- [Installation](#installation)
- [Configuration](#configuration)
- [Development Setup](#development-setup)
- [Contributing](#contributing)
- [License](#license)
- [Acknowledgments](#acknowledgments)

Vector Inspector bridges the gap between vector databases and user-friendly data exploration tools. While vector databases are powerful for semantic search and AI applications, they often lack the intuitive inspection and management tools that traditional SQL databases have. This project aims to provide that missing layer.

## Key Features

### 1. **Multi-Provider Support**
- Connect to vector databases:
  - ChromaDB (persistent local storage)
  - Qdrant (remote server or embedded local)
- Unified interface regardless of backend provider
- Automatically saves last connection configuration

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

Vector Inspector is built with PySide6 (Qt for Python) for the GUI, providing a native desktop experience. The backend uses Python with support for multiple vector database providers through a unified interface.

For detailed architecture information, see [docs/architecture.md](docs/architecture.md).

## Use Cases

1. **AI/ML Development**: Inspect embeddings generated during model development
2. **RAG System Debugging**: Verify what documents are being retrieved
3. **Data Quality Assurance**: Identify poorly embedded or outlier vectors
4. **Production Monitoring**: Check vector database health and data consistency
5. **Data Migration**: Transfer data between vector database providers
6. **Education**: Learn and experiment with vector databases interactively

## Feature Access

Vector Inspector is available in both free (open source) and Pro versions. The free version includes all core features for ChromaDB and basic Qdrant support, while Pro adds advanced analytics and additional providers.

See [FEATURES.md](FEATURES.md) for a complete feature comparison.

## Roadmap

**Current Status**: ✅ Phase 2 Complete

See [ROADMAP.md](ROADMAP.md) for the complete development roadmap and planned features.

## Installation

### From PyPI (Recommended)

```bash
pip install vector-inspector
vector-inspector
```

### From Source

```bash
# Clone the repository
git clone https://github.com/anthonypdawson/vector-viewer.git
cd vector-viewer

# Install dependencies using PDM
pdm install

# Launch application
./run.sh     # Linux/macOS
./run.bat    # Windows
```

## Configuration

Paths are resolved relative to the project root (where `pyproject.toml` is). For example, entering `./data/chroma_db` will use the absolute path resolved from the project root.

The application automatically saves your last connection configuration to `~/.vector-viewer/settings.json`. The next time you launch the application, it will attempt to reconnect using the last saved settings.

Example settings structure:
```json
{
  "last_connection": {
    "provider": "chromadb",
    "connection_type": "persistent",
    "path": "./data/chroma_db"
  }
}
```

## Development Setup

```bash
# Install PDM if you haven't already
pip install pdm

# Install dependencies with development tools (PDM will create venv automatically)
pdm install -d

# Run tests
pdm run pytest

# Run application in development mode
./run.sh     # Linux/macOS
./run.bat    # Windows

# Or use Python module directly from src directory:
cd src
pdm run python -m vector_viewer
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
