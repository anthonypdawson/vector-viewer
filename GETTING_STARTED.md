# Getting Started with Vector Viewer

## Phase 1 Implementation Complete! 🎉

All Phase 1 features have been implemented:
- ✅ Connection to ChromaDB
- ✅ Basic metadata browsing and filtering
- ✅ Simple similarity search interface
- ✅ 2D vector visualization (PCA/t-SNE/UMAP)
- ✅ Basic CRUD operations

## Quick Start

### 1. Install Dependencies

```bash
pdm install -d
```

### 2. Create Sample Data (Optional)

Run the sample data script to populate a test ChromaDB database:

```bash
pdm run python create_sample_data.py
```

This will create a `./chroma_data` directory with sample documents.

### 3. Run the Application

**Option 1: Using the run script (recommended)**

On Windows:
```bash
./run.bat
```

On Linux/Mac:
```bash
chmod +x run.sh
./run.sh
```

**Option 2: Direct command**

```bash
cd src
pdm run python -m vector_viewer.main
```

## Using the Application

### Connecting to ChromaDB

1. Click "Connect" button or use File > Connect to Database
2. Choose connection type:
    - **Persistent (Local File)**: For local ChromaDB storage (recommended for testing)
       - Default path: `./data/chrome_db` (resolved relative to the project root)
       - The dialog shows the resolved absolute path so you know exactly where data is read/written
    - **HTTP (Remote Server)**: For ChromaDB server instances
    - **Ephemeral (In-Memory)**: Temporary database (data lost on disconnect)
3. Click "Connect"

### Browsing Data

1. Select a collection from the left panel
2. Use the "Data Browser" tab to:
   - View all items with metadata
   - Page through data
   - Delete selected items
   - Add new items

### Searching

1. Go to the "Search" tab
2. Enter text to search for similar vectors
3. Adjust number of results
4. Click "Search"
5. Results show similarity distances and metadata

### Visualizing Vectors

1. Go to the "Visualization" tab
2. Select dimensionality reduction method:
   - **PCA**: Fast, linear reduction
   - **t-SNE**: Better for clusters, slower
   - **UMAP**: Good balance of speed and quality
3. Choose 2D or 3D
4. Set sample size (larger = slower but more complete)
5. Click "Generate Visualization"
6. The plot will open in your default web browser

## Project Structure

```
src/vector_viewer/
├── main.py                    # Application entry point
├── core/
│   └── connections/
│       └── chroma_connection.py   # ChromaDB connection manager
├── ui/
│   ├── main_window.py         # Main application window
│   ├── components/
│   │   └── item_dialog.py     # Add/edit item dialog
│   └── views/
│       ├── connection_view.py     # Connection panel
│       ├── collection_browser.py  # Collection list
│       ├── metadata_view.py       # Data browser
│       ├── search_view.py         # Search interface
│       └── visualization_view.py  # Vector visualization
└── services/
    └── visualization_service.py   # Dimensionality reduction
```

## Features Implemented

### Connection Management
- Connect to persistent, HTTP, or ephemeral ChromaDB instances
- Save connection settings
- View connection status

### Collection Browser
- List all collections
- View collection statistics
- Select collections for viewing
- Delete collections (with context menu)

### Data Browser
- Paginated table view of items
- View IDs, documents, and metadata
- Sort and select rows
- Add new items with metadata
- Delete selected items

### Search
- Text-based similarity search
- Configurable number of results
- View similarity distances
- Display full document and metadata

### Visualization
- PCA, t-SNE, and UMAP dimensionality reduction
- 2D and 3D plotting
- Interactive plots with Plotly
- Hover to see item details
- Configurable sample sizes

## Next Steps (Phase 2+)

- Add more vector database providers (Pinecone, Weaviate, Qdrant)
- Advanced filtering and query builder
- Embedding model integration
- Import/export functionality
- Performance monitoring
- Cluster analysis tools

## Troubleshooting

### ChromaDB Not Found
Make sure chromadb is installed: `pdm install`

### No Data in Collection
Use the sample data script or add items manually through the UI

### Visualization Too Slow
- Reduce sample size
- Use PCA instead of t-SNE/UMAP
- Consider using fewer dimensions (2D vs 3D)

### Application Won't Start
- Ensure you're in the virtual environment: `pdm run`
- Check that all dependencies are installed: `pdm install -d`
- Look for error messages in the terminal

## Contributing

Contributions are welcome! Feel free to:
- Report bugs
- Suggest features
- Submit pull requests
- Improve documentation

## License

MIT License - See LICENSE file for details.
