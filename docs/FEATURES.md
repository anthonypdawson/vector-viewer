# Feature Access (Free vs Pro)

## Philosophy

Vector Inspector follows a user-friendly monetization model:

- **All vector database providers are free** — Pinecone, Weaviate, ChromaDB, Qdrant, Milvus, FAISS, pgvector, Elasticsearch, and any future providers
- **Core workflows remain free** — Connect, browse, search, visualize, filter, and manage your data
- **Pro features add power tools** — Advanced analytics, workflow automation, enterprise formats, and collaboration

This approach ensures you can **try and use the entire app** with any provider, while Pro adds depth for teams and advanced use cases.

## Feature Comparison

### 🌍 Vector Database Providers (All Free)

| Provider                                     | Access   | Notes                                      |
|----------------------------------------------|----------|--------------------------------------------|
| ChromaDB                                     | Free     | Persistent local or remote                 |
| Qdrant                                       | Free     | Local, remote, or cloud                    |
| Pinecone                                     | Free     | Cloud-hosted vector database               |
| Weaviate                                     | Free     | Local or cloud with GraphQL                |
| Milvus                                       | Free     | Distributed vector database                |
| FAISS (local files)                          | Free     | Facebook's similarity search library       |
| pgvector (PostgreSQL)                        | Free     | Postgres extension for vectors             |
| Elasticsearch (vector search)                | Free     | Elasticsearch with KNN plugin              |

> **All providers get the same core feature set:** connect, browse, search, visualize, CRUD, import/export (CSV/JSON), metadata filtering.

---

### 🎯 Core Features (Free)

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Connection management                        | Free     | Connect to any supported provider          |
| Collection/index browsing                    | Free     | View all collections with statistics       |
| Metadata browsing & filtering                | Free     | Advanced filters, AND/OR logic             |
| Similarity search                            | Free     | Text-to-vector                             |
| 2D visualization (PCA/t-SNE/UMAP)            | Free     | Dimensionality reduction plots             |
| 3D visualization                             | Free     | Interactive 3D scatter plots               |
| CRUD operations                              | Free     | Create, read, update, delete vectors       |
| Item editing                                 | Free     | Edit metadata and documents inline         |
| Import/Export (CSV, JSON)                    | Free     | Standard data formats                      |
| Backup & restore                             | Free     | Collection-level backup/restore            |
| Cross-database migration                     | Free     | Migrate collections between providers      |
| Query history                                | Free     | Recent queries (last 10–20)                |
| Basic embedding integration                  | Free     | Local models, simple API calls             |
| Advanced query builder                       | Free     | Visual filter builder with preview         |
| Schema inspector                             | Free     | View collection config and metadata        |

---

### ⚡ Pro Features (Power Tools & Workflows)

#### 📊 Advanced Data Formats & Import/Export

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Parquet import/export                        | Pro      | Enterprise schema-aware format             |
| Bulk import/export pipelines                 | Pro      | Large-scale data migration tools           |
| Schema-aware import/export                   | Pro      | Automatic type detection and mapping       |

#### 🔍 Advanced Queries & Search

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Saved queries (named, persistent)            | Pro      | Save and share query templates             |
| Similarity search                            | Pro      | Vector-to-vector                           |
| Cross-collection queries                     | Pro      | Query across multiple collections          |
| Query templates                              | Pro      | Reusable query patterns                    |
| Nested condition builder                     | Pro      | Complex boolean logic with nesting         |

#### 🧠 Embedding & Model Tools

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Model Comparison Mode                        | Pro      | Compare embeddings from different models   |
| Embedding Inspector                          | Pro      | Analyze which dimensions drive similarity  |
| Large batch embedding jobs                   | Pro      | Process thousands of items                 |
| Multiple model selection                     | Pro      | Switch between embedding models            |
| Embedding pipelines                          | Pro      | Automated embedding workflows              |
| GPU-accelerated workflows                    | Pro      | Hardware acceleration for embeddings       |

#### 📈 Analytics & Insights

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Cluster Explorer                             | Pro      | Advanced clustering with DBSCAN, HDBSCAN   |
| Embedding Provenance Graph                   | Pro      | Track embedding lineage and transformations|
| Semantic Drift Timeline                      | Pro      | Monitor how embeddings change over time    |
| Cross-Collection Similarity                  | Pro      | Find similar items across databases        |
| Performance profiling                        | Pro      | Query optimization and index analysis      |

#### 🏢 Enterprise & Provider Features

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Cloud authentication flows                   | Pro      | OAuth, API key management for cloud DBs    |
| Advanced payload filtering                   | Pro      | Provider-specific advanced queries         |
| Hybrid search (semantic + keyword)           | Pro      | Combined search strategies                 |
| Sharding/replica insights                    | Pro      | Cluster-level metadata and diagnostics     |
| Index statistics & optimization              | Pro      | Performance tuning and monitoring          |

#### 🛠️ Power Tools

| Feature                                      | Access   | Description                                |
|----------------------------------------------|----------|--------------------------------------------|
| Vector Surgery                               | Pro      | Modify vector dimensions directly          |
| Custom plugin system                         | Pro      | Extend app with custom features            |
| Team collaboration                           | Pro      | Share queries, collections, and workspaces |
| Audit logging                                | Pro      | Track all changes and queries              |
| API access (programmatic)                    | Pro      | REST API for automation                    |

---

## Summary

**Free tier gives you:**
- Full access to all vector database providers
- Complete data management (CRUD, import/export, backup)
- Visualization and exploration tools
- Search and filtering
- Query history and basic workflows

**Pro tier adds:**
- Enterprise data formats (Parquet)
- Advanced analytics and insights
- Workflow automation and pipelines
- Team collaboration
- Provider-specific power features
- Custom extensions

> **Nothing currently in Free will ever move to Pro.** This is our commitment to users.
