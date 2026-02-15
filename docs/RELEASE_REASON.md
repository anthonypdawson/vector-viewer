## Release Notes (0.3.16)

### Data Browser
- Fixed pagination bug: The "Next" button is now correctly disabled when there is no more data, preventing navigation to empty pages.
- Row numbers in the table now reflect the absolute index across all pages (vertical header shows correct item number).
- In Data browser -> Add right click -> 'Copy vector to JSON' for easy copying of vector data for debugging and sharing
- Unify right click menu between Data Browser and Search results
- **Enhanced item details dialog**: When double-clicking a row in Data Browser or Search results, the details dialog now shows additional information including:
  - Creation and update timestamps (extracted from metadata fields like `created_at`, `updated_at`)
  - Embedding dimensions prominently displayed
  - Cluster assignment (if available in metadata)
  - Additional similarity metrics for search results (dot product, cosine similarity)
  - Filtered metadata view (fields shown separately are excluded from the metadata JSON display)
- **Automatic timestamp injection**: (Optionally) When adding or editing items through the Data Browser:
  - New items can optionally get a `created_at` timestamp in ISO format
  - Edited items can optionally get an `updated_at` timestamp in ISO format
  - A checkbox toggle in the add/edit dialog controls whether timestamps are automatically added (default: enabled)
  - Timestamps are stored in item metadata and displayed in the details dialog
  - Default: Disabled to avoid unintended metadata changes but encouraged for better tracking of item history

### Visualization
- **Save cluster labels to metadata**: After running clustering algorithms (KMeans, HDBSCAN, DBSCAN, OPTICS), cluster assignments can now be saved back to the database
  - New "Save labels to metadata" checkbox in the Clustering panel (unchecked by default)
  - Cluster IDs are saved as a `cluster` field in item metadata
  - Saved cluster assignments are visible in the Data Browser details dialog
  - Updated items also get an `updated_at` timestamp when cluster labels are saved
- **View in Data Browser**: Added a "View in Data Browser" button to the visualization plot toolbar. When a user selects a point in the 2D (not 3d for now) plot and clicks this button, it emits a signal with the corresponding item ID. The main window listens for this signal, switches to the Data Browser tab, and selects the corresponding row based on the item ID. This allows users to easily navigate from a point in the visualization to its detailed view in the Data Browser.

### Embedding Models
- Added disk caching for embedding models (SentenceTransformers and HuggingFace-based models). Models are saved to a local cache to speed up repeated imports and searches; a new Settings control lets users view and clear the embedding model cache.

- Added unit tests for new changes

---