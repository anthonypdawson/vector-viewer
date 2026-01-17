# Changelog

All notable changes to Vector Viewer will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-17

### Added - Phase 1 Implementation

#### Core Features
- ChromaDB connection manager with support for persistent, HTTP, and ephemeral connections
- Main application window with tabbed interface (PySide6)
- Connection configuration dialog
- Collection browser with list, select, and delete functionality
- Data browser with paginated table view
- Item addition dialog with JSON metadata support
- Item deletion (single and batch)
- Text-based similarity search interface
- Vector visualization with three dimensionality reduction methods (PCA, t-SNE, UMAP)
- 2D and 3D interactive plotting with Plotly
- Background processing for dimensionality reduction

#### User Interface
- Professional Qt-based GUI
- Main menu bar with File, Collection, and Help menus
- Toolbar with quick actions
- Status bar with connection and collection status
- Left panel for connection and collections
- Right panel with three tabs: Data Browser, Search, Visualization
- Responsive layout with splitters

#### Documentation
- Comprehensive README.md with project overview
- GETTING_STARTED.md with installation and usage instructions
- IMPLEMENTATION_SUMMARY.md with technical details
- QUICK_REFERENCE.md for common tasks
- PROJECT_STATUS.md tracking development progress
- Inline code documentation with docstrings

#### Developer Tools
- PDM project configuration
- Sample data generation script
- Run scripts for Windows (.bat) and Unix (.sh)
- Development dependencies configured (pytest, black, ruff, mypy)

### Technical Details

#### Dependencies
- chromadb >= 0.4.22
- pyside6 >= 6.6.0
- pandas >= 2.1.0
- numpy >= 1.26.0
- scikit-learn >= 1.3.0
- umap-learn >= 0.5.5
- plotly >= 5.18.0
- sentence-transformers >= 2.2.0

#### Architecture
- Modular structure with separation of concerns
- Core layer for database operations
- UI layer for interface components
- Services layer for business logic
- Signal/slot pattern for component communication

### Testing
- Manual testing of all core features
- Verified with sample dataset
- All visualization methods tested (PCA, t-SNE, UMAP)
- CRUD operations validated

## [Unreleased] - Future Versions

### Planned for 0.2.0 (Phase 2)
- Advanced metadata filtering
- Item editing functionality
- Import/export (CSV, JSON)
- Multiple vector database providers (Pinecone, Weaviate, Qdrant)
- Enhanced visualizations with color-by-metadata
- Query history and saved queries
- Automated test suite

### Planned for 0.3.0 (Phase 3)
- Cluster analysis tools
- Performance monitoring dashboard
- Bulk operations interface
- Custom plugin system
- Configuration management
- Dark mode theme

### Planned for 1.0.0 (Phase 4)
- Production-ready release
- Complete test coverage (>80%)
- User manual and tutorials
- Installer/packaging
- Multi-user support
- Audit logging

## Version History

- **0.1.0** (2026-01-17) - Initial Phase 1 release ✅

---

[0.1.0]: https://github.com/yourusername/vector-viewer/releases/tag/v0.1.0
