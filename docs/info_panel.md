# Unified Information Panel Design

A unified information panel provides a single, always-visible view of both database-level and collection-level details. This "instrument readout" is essential for transparency, troubleshooting, and professional UX in Vector Inspector.

## Default Panel & Tab Structure
- The Info panel will be the **default tab** shown when the application starts or when a new connection is made.
- The main tabs in the application will be:
  1. **Info** (default)
  2. **Data Browser**
  3. **Search**
  4. **Visualization**
- The Info tab is being added to the existing set of tabs, providing immediate context before users interact with data or search features.

## Purpose
- Give users a clean, declarative snapshot of the current environment
- Eliminate the need to hunt for structural or metadata details
- Support forensic, migration, and debugging workflows
- Raise trust and usability to the level of mature database GUIs

## Panel Structure

### 1. Database Information
- **Provider:** (e.g., Qdrant, Chroma, Postgres)
- **Host & Port:** Connection endpoint
- **API Key Status:** (present/absent, never show the key itself)
- **Server Version:** (if available)
- **Uptime / Health Status:** (if available)
- **Available Collections:** List of all collections in the database

### 2. Collection Information (for selected collection)
- **Collection Name**
- **Vector Dimension**
- **Distance Metric** (e.g., cosine, Euclidean)
- **Total Points / Vectors**
- **Payload Schema:** Keys and inferred types for metadata fields
- **Indexing Config:** HNSW or other index settings
- **Provider-Specific Details:** Any quirks, limits, or special features

## UX Goals
- Always visible or one-click accessible (as the first tab)
- Read-only, declarative (not editable here)
- Updates live as user changes connection or collection
- Grouped visually: database info at top, collection info below
- Clear error or warning if any info is unavailable

## Why This Matters
- Current state: Metadata is visible, but structural info is scattered or hidden
- This panel solves a key UX tension by consolidating all critical facts
- Makes Vector Inspector feel like a true professional tool for data science, ML, and engineering

## Example Layout

```
+-----------------------------+
| Database: Qdrant            |
| Host: localhost:6333        |
| API Key: Present            |
| Version: 1.7.0              |
| Uptime: 2d 4h 12m           |
| Collections:                |
|   - users                   |
|   - products                |
+-----------------------------+
| Collection: products        |
| Dimension: 384              |
| Distance: cosine            |
| Total Points: 120,000       |
| Schema:                     |
|   - id: string              |
|   - price: float            |
|   - tags: list[string]      |
| Index: HNSW (M=16, ef=200)  |
| Provider Quirks:            |
|   - Max vectors: 10M        |
+-----------------------------+
```

---

*This panel is a must-have for any serious vector database tool. It provides the essential context for every user action and supports advanced troubleshooting and analysis.*
