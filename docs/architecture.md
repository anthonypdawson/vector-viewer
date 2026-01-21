# Architecture

## Technology Stack

### Frontend (GUI)
- **Framework**: PySide6 (Qt for Python) - native desktop application
- **UI Components**: Qt Widgets for forms, dialogs, and application structure
- **Visualization**: 
  - Plotly for interactive charts (embedded via QWebEngineView)
  - matplotlib for static visualizations
- **Data Grid**: QTableView with custom models for high-performance data display

### Backend
- **Language**: Python 3.12
- **Core Libraries**:
  - Vector DB clients: `chromadb`, `qdrant-client` (implemented), `pinecone-client`, `weaviate-client`, `pymilvus` (planned)
  - Embeddings: `sentence-transformers`, `fastembed` (implemented), `openai`, `cohere` (planned)
  - Data processing: `pandas`, `numpy`
  - Dimensionality reduction: `scikit-learn`, `umap-learn`
- **API Layer**: FastAPI (planned for programmatic access) or direct Python integration

### Data Layer
- **Connection Management**: Provider-specific connection classes with unified interface
- **Query Abstraction**: Base connection interface that each provider implements
- **Storage Modes**:
  - ChromaDB: Persistent local storage
  - Qdrant Remote: Connect via host/port (e.g., localhost:6333)
  - Qdrant Embedded: Local path storage without separate server
- **Caching**: Redis or in-memory cache for frequently accessed data (planned)
- **Settings Persistence**: User settings saved to ~/.vector-viewer/settings.json

## Application Structure

```
vector-viewer/
├── src/
│   └── vector_inspector/
│       ├── core/
│       │   └── connections/   # Connection managers for each provider
│       ├── ui/
│       │   ├── components/    # Reusable UI components
│       │   └── views/         # Main application views
│       ├── services/          # Business logic services
│       └── main.py            # Application entry point
├── tests/
├── docs/
├── data/                      # Local database storage
│   ├── chroma_db/
│   └── qdrant/
├── run.sh / run.bat           # Launch scripts
└── pyproject.toml
```

User settings are saved to `~/.vector-viewer/settings.json`

## Risks & Mitigations

### UI Complexity Creep
- **Risk:** As features grow, business logic may leak into views, making the UI layer hard to maintain.
- **Mitigation:** Keep heavy logic in services; maintain thin views. Consider adopting a ViewModel/presenter pattern if complexity increases.

### Provider Divergence
- **Risk:** Backend-specific quirks (e.g., tag filtering, distance metrics) may leak into higher-level logic, reducing maintainability.
- **Mitigation:** Normalize provider capabilities explicitly. Define a capability matrix and ensure all provider differences are handled at the connection/service layer.

### Visualization Scalability
- **Risk:** Dimensionality reduction (DR) and plotting may not scale to large datasets, impacting performance and UX.
- **Mitigation:** Choose and document a default DR method (e.g., UMAP/TSNE). For large N, precompute or sample data, and document limits/fallbacks in the code and user docs.
