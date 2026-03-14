# Provider/Model Comparison Mode
Feature: Diff Mode for Providers and Models
Version: Draft  
Owner: Anthony Dawson  
Status: Proposed for 0.7.x  

## Overview
Provider/Model Comparison Mode introduces a unified workflow for comparing the behavior of two vector search configurations. Users can compare:

- Two providers (e.g., Chroma vs Qdrant)
- Two embedding models (e.g., text-embedding-3-small vs bge-large)
- Two provider+model combinations
- Two settings profiles (e.g., cosine vs dot-product, normalization on/off)

The goal is to give developers a forensic, side-by-side view of how different vector search stacks behave under identical queries. This feature elevates Vector Inspector from a single-provider debugger into a full evaluation and benchmarking tool.

## Problem Statement
Teams building RAG systems often need to answer questions like:

- “Will switching providers change our ranking behavior?”
- “Does Model B retrieve more relevant results than Model A?”
- “Why does provider X return this document but provider Y doesn’t?”
- “How different are the embeddings between these two models?”

Today, answering these questions requires custom scripts, manual comparisons, or guesswork. Vector Inspector can automate and visualize this entire workflow.

## Goals
- Provide a clear, intuitive UI for comparing two search configurations.
- Highlight differences in ranking, missing hits, and score deltas.
- Allow users to compare embeddings directly (vector diff).
- Integrate Ask the AI to explain differences.
- Support any provider/model combination supported by Vector Inspector.

## Non-Goals
- Full benchmarking suite (latency, throughput) — may come later.
- Automated model selection or recommendations.
- Persisted comparison sessions (future enhancement).

## User Stories
1. As an ML engineer, I want to compare two providers side-by-side so I can validate a migration.
2. As a researcher, I want to compare two embedding models to understand semantic drift.
3. As a developer, I want to see which results appear in one provider but not the other.
4. As a product owner, I want to understand how different configurations affect relevance.

## Core Features

### 1. Comparison Selector
A new panel allowing users to choose:
- Provider A + Model A
- Provider B + Model B

Each side includes:
- Provider dropdown
- Model dropdown
- Settings (metric, normalization, top_k, etc.)

### 2. Side-by-Side Search Results
A dual-column layout:
- Left: Results from Configuration A
- Right: Results from Configuration B

Each result row includes:
- Document ID
- Score
- Highlighted differences (missing, reordered, score delta)

### 3. Difference Highlighting
Visual indicators:
- Green: Appears in both with similar rank
- Yellow: Appears in both but rank shifted significantly
- Red: Appears only in one configuration

Optional: “Align by document ID” mode.

### 4. Embedding Comparison
For a given query or document:
- Show embedding vectors for A and B
- Compute cosine similarity between embeddings
- Visualize differences (heatmap, delta vector, or simple numeric diff)

### 5. Ask the AI: Explain the Difference
A new button:
“Explain why these results differ”

The AI can analyze:
- Embedding differences
- Provider scoring behavior
- Ranking shifts
- Missing hits
- Semantic drift

### 6. Context Preview (Dual)
Show the exact payload sent to each provider/model:
- Query text
- Embedding
- Settings
- Provider request body

## Architecture

### Data Model
ComparisonSession:
- id
- configA: ProviderConfig
- configB: ProviderConfig
- query: string
- resultsA: SearchResult[]
- resultsB: SearchResult[]
- embeddingA: number[]
- embeddingB: number[]
- metadata: timestamps, provider info

### Frontend Components
- ComparisonSelector
- ComparisonResultsGrid
- EmbeddingDiffPanel
- ExplainDifferenceDialog
- ContextPreviewDual

## UX Flow
1. User selects “Comparison Mode” from the sidebar.
2. User configures A and B.
3. User enters a query.
4. Results appear side-by-side.
5. User toggles “Highlight Differences.”
6. User optionally opens:
   - Embedding Diff
   - Context Preview
   - Ask the AI

## Future Enhancements
- Latency benchmarking
- Multi-query batch comparison
- Export comparison report
- Persisted comparison sessions
- “Best match” recommendations

## Risks
- Increased API load (two searches per query)
- UI complexity
- Provider inconsistencies (different metadata formats)

## Design Considerations & Recommendations

### UI Complexity
The dual-column layout and difference highlighting can become visually dense, especially with large result sets. Consider:
- Pagination or virtualized scrolling
- A toggle to collapse unchanged rows
- A “differences only” filter to reduce noise

These controls help maintain clarity without sacrificing detail.

### Provider/Model Abstraction
Providers often return different metadata schemas, scoring formats, or document structures. The comparison engine should:
- Normalize common fields (id, score, text, metadata)
- Gracefully handle missing or provider-specific fields
- Use a flexible adapter pattern to support future providers

This ensures long-term robustness as the ecosystem expands.

### Performance
Running two queries per user action may impact responsiveness. To keep the UI fast:
- Cache embeddings and previous queries
- Batch requests when possible
- Load secondary results in the background
- Defer expensive diff computations until needed

Responsiveness is critical for a forensic debugging workflow.

### Explainability (Ask the AI)
Start with simple, template-driven explanations for differences:
- “Provider A returned X because…”
- “Model B ranks Y higher due to…”

Iterate toward deeper semantic analysis as usage patterns emerge. A phased approach manages complexity and sets realistic expectations.

### Testing
Comparison logic is inherently brittle without strong test coverage. Prioritize:
- Unit tests for diffing and alignment
- Golden-file tests for result highlighting
- Provider-specific integration tests
- Regression tests as new providers/models are added

This protects the feature as the matrix of supported configurations grows.

### Non-Goals Extensibility
While benchmarking and session persistence are out of scope for the initial release, design the architecture so they can be added later without major refactoring. Keep:
- ComparisonSession as a first-class data model
- Clear separation between UI, diff logic, and provider adapters
- Hooks for future metrics (latency, token usage, etc.)

This ensures the feature can evolve into a full evaluation suite over time.

## Implementation Challenges & Considerations

### UI Complexity
- **Pagination/Virtualization:** Implementing efficient virtualized tables in Qt (PySide6) can be non-trivial, especially with custom cell rendering for highlights and diffs. You may need to extend `QTableView`/`QAbstractTableModel` and handle custom painting.
- **Collapse/Filter Controls:** Adding toggles and filters is straightforward, but keeping the UI responsive with large datasets requires careful state management and possibly background diff computation.

### Provider/Model Abstraction
- **Normalization:** Providers may have subtle differences in how they represent IDs, scores, or metadata. Building robust adapters will require comprehensive test cases and handling provider-specific quirks.
- **Missing Fields:** Graceful degradation is important, but you’ll need clear UI cues for “missing” or “not available” fields to avoid user confusion.
- **Adapter Pattern:** Maintaining adapters as providers evolve will require ongoing diligence and version tracking.

### Performance
- **Caching:** Embedding and result caching is effective, but cache invalidation (when settings or models change) must be handled carefully to avoid stale data.
- **Batching/Background Loading:** Threading in PySide6 is safe if you use `QThread` and signals/slots, but you must avoid UI updates from background threads.
- **Deferred Diffing:** Users may expect instant feedback; communicate when expensive operations are deferred or in progress.

### Explainability (Ask the AI)
- **Template-Driven Explanations:** Easy to start, but as you move to deeper analysis, you’ll need to design a clear interface between the comparison engine and the LLM (e.g., what context is sent, how much data, privacy concerns).
- **LLM Cost/Latency:** If using cloud LLMs, consider rate limits, cost, and user feedback for slow responses.

### Testing
- **Golden-File Tests:** These are great for regression, but maintaining them as providers/models change can be labor-intensive.
- **Integration Tests:** Mocking provider responses for all edge cases is important, especially for error handling and missing data.

### Non-Goals Extensibility
- **Hooks for Future Metrics:** Design your data models and APIs to be forward-compatible (e.g., allow for new fields without breaking consumers).
- **Session Persistence:** If you plan to add this later, keep session state management modular.

**Summary:**  
No fundamental blockers, but the main risks are around UI performance with large datasets, provider heterogeneity, and keeping the system maintainable as new providers/models are added. Strong test coverage, modular design, and clear user feedback for slow/expensive operations will be key to success.

## Success Metrics
- Adoption rate of Comparison Mode
- Reduction in debugging time for provider/model migrations
- User feedback on clarity of differences
- Increased usage of Ask the AI for explanations
