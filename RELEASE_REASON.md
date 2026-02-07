# Latest updates

## February 7, 2026 Release Summary

### New Features
- **Create Collection With Sample Data**: Added dialog and backend logic to create collections with synthetic text, markdown, or JSON sample data. Supports embedding model selection and generates embeddings automatically.
- **Threaded Collection Creation**: Collection creation and sample data population now run in a background thread, keeping the UI responsive.
- **Loading Dialog**: Progress dialog appears immediately and updates through all steps (model loading, collection creation, data insertion).
- **Embedding Model Tracking**: The selected embedding model is now saved per collection and profile, so the app shows the actual model used instead of 'autodetect'.

### Bug Fixes & Improvements
- Fixed syntax errors and API misuse in collection_service.py and connection_controller.py
- Improved error handling and logging for collection creation
- UI feedback for success/failure is more informative

### Technical Notes
- Refactored to use VectorDBConnection abstract API for all provider operations
- All new/modified files checked for syntax errors
- Model registry and settings integration for embedding model persistence

## Vector Studio
 - Added support for clustering visualization with HDBSCAN, DBScan, OPTICS, KMeans (Premium feature)
---