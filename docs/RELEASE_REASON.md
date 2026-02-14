## Release Notes (0.3.16)

### Data Browser
- Fixed pagination bug: The "Next" button is now correctly disabled when there is no more data, preventing navigation to empty pages.
- Row numbers in the table now reflect the absolute index across all pages (vertical header shows correct item number).
- In Data browser -> Add right click -> 'Copy vector to JSON' for easy copying of vector data for debugging and sharing
- Unify right click menu between Data Browser and Search results

### Embedding Models
- Added disk caching for embedding models (SentenceTransformers and HuggingFace-based models). Models are saved to a local cache to speed up repeated imports and searches; a new Settings control lets users view and clear the embedding model cache.

---