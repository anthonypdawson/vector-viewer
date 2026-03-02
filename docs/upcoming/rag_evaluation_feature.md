# Vector Inspector — RAG Evaluation Feature Design

## The Core Idea

Extend Vector Inspector from a passive data inspection tool into an active **RAG pipeline evaluation framework**. The key differentiator: because Vector Inspector already speaks to multiple vector databases and can migrate/re-embed collections, it can answer questions no other tool can:

- *"Does my data perform better with model X or model Y?"*
- *"Is Qdrant or ChromaDB a better fit for my specific dataset?"*
- *"Is my current embedding model actually good for my use case?"*

All evaluation runs locally — no API keys required, no data leaves the machine. A local LLM acts as the judge.

---

## What Makes This Unique

Most RAG evaluation tools (Ragas, TruLens, etc.) require:
- Ground truth datasets set up in advance
- A single database/model combination
- External API calls for evaluation

Vector Inspector's approach:
- Uses existing collections as the starting point
- Clones and re-embeds automatically (code already exists)
- Works across all supported databases in a unified interface
- Local LLM does the judging — no external dependencies
- Database-agnostic: compare across providers, not just within one

**Positioning:** *"Find the best model and database for your specific data"* — not benchmarks on someone else's dataset, your actual data, your actual queries.

---

## The Workflow

### Step 1 — Select Source Collection
User picks an existing collection as the baseline. This is the "control" in the experiment.

### Step 2 — Define What to Test
User specifies what they're changing:
- **Embedding model** (e.g. `all-MiniLM` vs `text-embedding-3-small`)
- **Vector database** (e.g. ChromaDB vs Qdrant)
- **Both**

This choice constrains subsequent steps (mirrors the existing "compatible collections" pattern from the histogram compare UI).

### Step 3 — Clone & Re-embed
Vector Inspector clones the source collection to the target DB, optionally re-embedding with the new model. This code already exists via the cross-DB migration feature.

### Step 4 — Generate or Provide Query Set
Two options:

**User-provided:** Import a list of queries (CSV, JSON). Most accurate for real-world use cases.

**Auto-generated (the interesting path):**
1. Sample representative documents from the collection
2. Use cluster-aware sampling (see below)
3. Send sampled documents to local LLM with a prompt to generate N realistic questions
4. Present generated queries to user for review, edit, and approval before evaluation runs

User review before running is important — auto-generated questions can be too literal or miss the actual use case. Giving the user a chance to curate means the results are more meaningful and they feel ownership over the outcome.

### Step 5 — Run Evaluation
For each query, run against both collections (baseline and clone) and collect:
- Top-K results from each
- Query latency
- Local LLM relevance judgment per result

### Step 6 — Cleanup
After evaluation completes, automatically delete the cloned collection(s) created for testing. User should be notified what will be deleted and given the option to keep a copy if they want to do further inspection (e.g. browse the re-embedded collection in the Data Browser). Cleanup should also run if the evaluation is cancelled mid-run — no orphaned collections left behind.

### Step 7 — Results
Clear winner declaration: *"Collection A wins on 3 of 4 metrics"*. Simple visual representation rather than a dashboard of graphs to interpret. Developers want an answer, not more data to synthesize.

---

## Scoring Dimensions

### Retrieval Quality (LLM-judged)
- **Relevance** of top-K results — primary metric, LLM scores each result
- **Diversity** — are results meaningfully different or near-duplicates
- **Coverage / Hit rate** — does the right answer appear in results at all

### Performance (collected during evaluation run)
- **Query latency** — already measurable during query execution
- **Index size / memory footprint** — free to collect

The LLM-as-judge relevance score is the most novel part. Performance metrics are nearly free since queries are already being run.

---

## Cluster-Aware Query Sampling

When auto-generating queries, random sampling risks producing questions about edge-case or unrepresentative content. A smarter approach:

1. Run clustering on the collection (code already exists)
2. Sample documents from each cluster, proportional to cluster size
3. This ensures generated questions cover the *core topics* of the collection, not outliers
4. The most "central" vectors (closest to each cluster centroid) are the best candidates

**Why this matters:** A collection about cooking shouldn't generate test queries about the one accidentally-indexed legal document. Cluster-aware sampling naturally produces questions that reflect what the collection is actually about.

This approach also uses existing infrastructure — dimensionality reduction, clustering (HDBSCAN, k-means, DBSCAN, OPTICS), and the vector analysis code are all already in the codebase.

---

## The Closed Loop

The elegance of the auto-generation approach is that the same local LLM:
1. Generates test questions from sampled documents
2. Evaluates how well retrieval answers those questions

No external dependencies. No ground truth dataset required. Works on any collection out of the box.

---

## UI Approach

Build on the existing "Compare with" histogram pattern — users already understand "pick something to compare against." Extend that mental model to "pick a collection that was re-embedded with a different model."

A **wizard/stepper UI** for the setup phase keeps each screen simple and can show/hide steps based on earlier choices (e.g. if same DB is selected, skip target DB configuration).

The results view should prioritize clarity over completeness — an overall winner with supporting evidence, not six graphs requiring interpretation.

---

## Vector Studio Limits

- Free: maximum 2 models/collections per evaluation run
- Free: maximum 10 queries per run, manual input only
- Free: relevance scoring only, default LLM model only
- Studio: unlimited comparisons and query set size
- Studio: auto-generated queries with cluster-aware sampling
- Studio: full scoring dimensions (relevance, diversity, coverage, latency, index size)
- Studio: LLM model selection, saved evaluation history

See [Feature Limitations](feature_limitations.md) for full details.

---

## Local LLM Integration

See the companion LLM Provider Architecture doc for full details. Summary:

- **No Ollama requirement** — llama-cpp-python runs entirely in-process, no separate server
- **Default model** ships/downloads on first use (e.g. Phi-3-mini, Qwen2.5-1.5B)
- **Provider abstraction** means Ollama, OpenAI, and llama-cpp are all interchangeable
- **Auto-detection order:** user config → Ollama if running → llama-cpp fallback
- **Configured in Settings → LLM section** (see Settings Architecture doc)

---

## Infrastructure Already Built

| Feature needed | Status |
|---|---|
| Multi-DB connectivity | ✅ Done |
| Cross-DB collection migration | ✅ Done |
| Re-embedding on migration | ✅ Done (needs UI surface) |
| Data sampling | ✅ Done |
| Clustering (HDBSCAN, k-means, etc.) | ✅ Done |
| Histogram comparison UI pattern | ✅ Done |
| Local LLM integration (Ollama) | 🔲 Needed |
| Query generation prompt | 🔲 Needed |
| Evaluation runner | 🔲 Needed |
| Results view | 🔲 Needed |
| Wizard/stepper UI | 🔲 Needed |

The hard infrastructure is largely done. This is mostly assembly + the evaluation layer.

---

## Why This Solves the Discovery Problem

Current positioning ("browse your vector DB") competes with database-specific dashboards. The evaluation positioning doesn't:

> *"Database-agnostic RAG evaluation that works across ChromaDB, Qdrant, Pinecone, LanceDB, PgVector, and Weaviate — using your actual data and your actual queries."*

That's a concrete enough value proposition to write a specific blog post, target RAG-focused communities, and have people immediately understand why they'd want it. "I tested my RAG pipeline across 4 embedding models — here's what I found" is a post that gets shared.
