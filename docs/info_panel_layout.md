# Info Panel - Visual Layout Reference

## Default State (Not Connected)

```
┌─────────────────────────────────────────────────────┐
│ Info | Data Browser | Search | Visualization       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ Database Information ────────────────────────┐ │
│  │ Provider:         Not connected               │ │
│  │ Connection Type:  N/A                         │ │
│  │ Endpoint:         N/A                         │ │
│  │ API Key:          N/A                         │ │
│  │ Status:           Disconnected                │ │
│  │ Total Collections: 0                          │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Available Collections ───────────────────────┐ │
│  │ No collections                                │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Collection Information ──────────────────────┐ │
│  │ Name:             No collection selected      │ │
│  │ Vector Dimension: N/A                         │ │
│  │ Distance Metric:  N/A                         │ │
│  │ Total Points:     0                           │ │
│  │                                               │ │
│  │ Payload Schema:                               │ │
│  │   N/A                                         │ │
│  │                                               │ │
│  │ Provider-Specific Details:                    │ │
│  │   N/A                                         │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Connected State (ChromaDB Example)

```
┌─────────────────────────────────────────────────────┐
│ Info | Data Browser | Search | Visualization       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ Database Information ────────────────────────┐ │
│  │ Provider:         ChromaDB                    │ │
│  │ Connection Type:  Persistent (Local)          │ │
│  │ Endpoint:         ./data/chroma_db            │ │
│  │ API Key:          Not required                │ │
│  │ Status:           Connected                   │ │
│  │ Total Collections: 3                          │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Available Collections ───────────────────────┐ │
│  │ • my_collection                               │ │
│  │ • test_data                                   │ │
│  │ • documents                                   │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Collection Information ──────────────────────┐ │
│  │ Name:             my_collection               │ │
│  │ Vector Dimension: 384                         │ │
│  │ Distance Metric:  Cosine (default)            │ │
│  │ Total Points:     1,250                       │ │
│  │                                               │ │
│  │ Payload Schema:                               │ │
│  │   • id                                        │ │
│  │   • text                                      │ │
│  │   • category                                  │ │
│  │   • timestamp                                 │ │
│  │                                               │ │
│  │ Provider-Specific Details:                    │ │
│  │   • Provider: ChromaDB                        │ │
│  │   • Supports: Documents, Metadata, Embeddings │ │
│  │   • Default embedding: all-MiniLM-L6-v2       │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Connected State (Qdrant Example)

```
┌─────────────────────────────────────────────────────┐
│ Info | Data Browser | Search | Visualization       │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌─ Database Information ────────────────────────┐ │
│  │ Provider:         Qdrant                      │ │
│  │ Connection Type:  Remote (Host)               │ │
│  │ Endpoint:         localhost:6333              │ │
│  │ API Key:          Not configured              │ │
│  │ Status:           Connected                   │ │
│  │ Total Collections: 2                          │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Available Collections ───────────────────────┐ │
│  │ • products                                    │ │
│  │ • users                                       │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
│  ┌─ Collection Information ──────────────────────┐ │
│  │ Name:             products                    │ │
│  │ Vector Dimension: 768                         │ │
│  │ Distance Metric:  Cosine                      │ │
│  │ Total Points:     120,000                     │ │
│  │                                               │ │
│  │ Payload Schema:                               │ │
│  │   • price                                     │ │
│  │   • tags                                      │ │
│  │   • category                                  │ │
│  │   • brand                                     │ │
│  │                                               │ │
│  │ Provider-Specific Details:                    │ │
│  │   • Provider: Qdrant                          │ │
│  │   • Supports: Points, Payload, Vectors        │ │
│  │   • HNSW M: 16                                │ │
│  │   • HNSW ef_construct: 200                    │ │
│  │   • Indexing threshold: 20000                 │ │
│  └───────────────────────────────────────────────┘ │
│                                                     │
└─────────────────────────────────────────────────────┘
```

## Key UI Features

### Visual Design
- **Grouped Sections**: Three main groups with clear borders
- **Bold Labels**: Field names are bold for easy scanning
- **Monospace Lists**: Collections and schema shown in monospace font
- **Color Coding**:
  - Normal text: Dark gray (#2c3e50)
  - Placeholder text: Light gray
  - Error text: Red
- **Scrollable**: Content scrolls vertically for smaller screens
- **Responsive**: Adjusts to window size

### Interaction
- **Read-Only**: All fields are display-only
- **Auto-Update**: Refreshes when:
  - Connection established
  - Collection selected
  - Collections refreshed
  - Connection disconnected
- **Always Accessible**: First tab in the application

### Information Hierarchy
1. **Database Level** (top)
   - Connection details
   - Overall status
   - All collections
2. **Collection Level** (middle/bottom)
   - Specific collection metadata
   - Vector configuration
   - Schema details
   - Provider quirks

---

This layout provides instant visibility into the database state and makes Vector Inspector feel like a professional database management tool.
