# Vector Viewer - Quick Reference

## Launch Application

**Windows:**
```bash
scripts/run.bat
```

**Linux/Mac:**
```bash
scripts/run.sh
```

## Keyboard Shortcuts

- `Ctrl+O` - Open connection dialog
- `Ctrl+N` - New collection
- `Ctrl+Q` - Quit application
- `F5` - Refresh collections

## Quick Workflow

### 1. Connect to Database
```
File > Connect to Database
→ Select "Persistent (Local File)"
→ Path: ./chroma_data
→ Click "Connect"
```

### 2. Browse Data
```
Select collection in left panel
→ "Data Browser" tab
→ Use pagination controls
→ Click "Add Item" or "Delete Selected"
```

### 3. Search
```
"Search" tab
→ Enter search text
→ Set result count
→ Click "Search"
```

### 4. Visualize
```
"Visualization" tab
→ Choose method (PCA/t-SNE/UMAP)
→ Select 2D or 3D
→ Set sample size
→ Click "Generate Visualization"
→ Plot opens in browser
```

## Connection Types

| Type | Use Case | Path/Host |
|------|----------|-----------|
| Persistent | Local database | ./chroma_data |
| HTTP | Remote server | localhost:8000 |
| Ephemeral | Temporary testing | (none) |

## Visualization Methods

| Method | Speed | Best For | Sample Size |
|--------|-------|----------|-------------|
| PCA | ⚡ Fast | Quick overview | 500-5000 |
| t-SNE | 🐌 Slow | Finding clusters | 100-1000 |
| UMAP | ⚡ Medium | Balanced view | 500-2000 |

## Tips & Tricks

### Performance
- Use PCA for large datasets (>2000 vectors)
- Lower sample size if visualization is slow
- Use pagination to browse large collections

### Search
- Search uses ChromaDB's embedding function automatically
- Results are ordered by similarity (lowest distance = most similar)
- Try different search terms to explore the vector space

### Data Management
- Always confirm before deleting items
- Metadata must be valid JSON format
- Documents are automatically embedded

### Visualization
- 2D plots are faster than 3D
- Hover over points to see details
- Plot opens in browser for full interactivity
- Save plot as PNG from browser

## Common Tasks

### Add Sample Data
```bash
pdm run python create_sample_data.py
```

### Create New Collection
```
Collection > New Collection
→ Enter name
→ OK
```

### Delete Collection
```
Right-click collection in list
→ Delete Collection
```

### Export Search Results
Currently not supported - Planned for Phase 2

### Change Theme
Currently not supported - Planned for Phase 2

## Troubleshooting

| Problem | Solution |
|---------|----------|
| App won't start | Run from project root: `./run.bat` |
| Can't connect | Check path exists for persistent connection |
| No collections | Create one or run sample data script |
| Visualization fails | Ensure collection has embeddings |
| Search returns nothing | Check collection has data |

## File Locations

- **Database**: `./chroma_data/` (persistent)
- **Temp plots**: System temp directory
- **Config**: (Not yet implemented)

## Support

- GitHub Issues: [Report bugs]
- Documentation: README.md, GETTING_STARTED.md
- Implementation Details: IMPLEMENTATION_SUMMARY.md

## Version

- **Current**: 0.1.0 (Phase 1)
- **Release Date**: January 2026
- **Status**: Beta - ready for testing
