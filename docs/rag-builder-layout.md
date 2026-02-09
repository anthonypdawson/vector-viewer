# RAG Builder — Complete Module Layout for Vector Inspector (Python)
# With detailed context for what each file is responsible for
```
vector_inspector/
│
├── rag/
│   │   __init__.py
│   │
│   │   engine.py
│   │       # The high-level RAG orchestrator.
│   │       # Coordinates chunking → embedding → indexing → retrieval → prompting → LLM.
│   │       # This is the "brain" that the UI and services call.
│   │
│   │   pipeline.py
│   │       # Defines the ProcessingPipeline class.
│   │       # Accepts a PipelineConfig and executes each step in order.
│   │       # Keeps the pipeline modular and testable.
│   │
│   │   config.py
│   │       # Dataclasses for pipeline configuration:
│   │       # - ChunkerConfig
│   │       # - EmbedderConfig
│   │       # - VectorStoreConfig
│   │       # - RetrieverConfig
│   │       # - LLMConfig
│   │       # Includes validation helpers and default presets.
│   │
│   │   adapters.py
│   │       # Thin adapters that connect the RAG builder to your existing systems:
│   │       # - EmbedderAdapter → wraps core.embedding_providers.*
│   │       # - VectorStoreAdapter → wraps core.connections.*
│   │       # - LLMAdapter → wraps core.model_registry + provider_factory
│   │       # These ensure the RAG builder uses your existing providers, not new ones.
│   │
│   ├── chunkers/
│   │       __init__.py
│   │       base.py
│   │           # Abstract Chunker interface.
│   │           # Defines the contract: chunk(text) → list[Chunk]
│   │
│   │       recursive.py
│   │           # Standard recursive text splitter.
│   │
│   │       semantic.py
│   │           # Optional: semantic chunking using embeddings.
│   │
│   │       regex.py
│   │           # Regex-based chunking (e.g., split on headings).
│   │
│   │       markdown.py
│   │           # Markdown-aware chunking (headings, lists, code blocks).
│   │
│   ├── embedders/
│   │       __init__.py
│   │       base.py
│   │           # Abstract Embedder interface.
│   │           # Defines embed(texts) → list[vectors]
│   │
│   │       embedder_adapter.py
│   │           # Wraps your existing embedding providers:
│   │           # core.embedding_providers.sentence_transformer_provider
│   │           # core.embedding_providers.clip_provider
│   │           # etc.
│   │           # Ensures the RAG builder uses your real embedding stack.
│   │
│   │       openai.py
│   │           # Optional: direct OpenAI embedder.
│   │
│   │       ollama.py
│   │           # Optional: local Ollama embedder.
│   │
│   │       local.py
│   │           # Optional: local CPU/GPU embedding models.
│   │
│   ├── vectorstores/
│   │       __init__.py
│   │       vectorstore_adapter.py
│   │           # Wraps your existing DB connections:
│   │           # core.connections.chroma_connection
│   │           # core.connections.qdrant_connection
│   │           # core.connections.pgvector_connection
│   │           # etc.
│   │           # Provides a unified interface:
│   │           # - index(embeddings, metadata)
│   │           # - search(query_embedding, top_k, filters)
│   │           # - get(ids)
│   │           # No new DB providers are created.
│   │
│   ├── retrievers/
│   │       __init__.py
│   │       basic.py
│   │           # Simple top-k retrieval.
│   │
│   │       threshold.py
│   │           # Retrieval with score thresholding.
│   │
│   │       rerank.py
│   │           # Optional: re-ranking using LLM or cross-encoder.
│   │
│   ├── llm/
│   │       __init__.py
│   │       base.py
│   │           # Abstract LLM interface.
│   │           # Defines generate(prompt) → text
│   │
│   │       llm_adapter.py
│   │           # Wraps your existing model registry + provider factory.
│   │           # Ensures the RAG builder uses the same LLMs as the rest of VI.
│   │
│   │       openai.py
│   │           # Optional: direct OpenAI LLM.
│   │
│   │       ollama.py
│   │           # Optional: local Ollama LLM.
│   │
│   │       mock.py
│   │           # Useful for testing pipelines without calling a real model.
│   │
│   ├── prompt/
│   │       __init__.py
│   │       assembler.py
│   │           # Builds the final prompt:
│   │           # system_template + retrieved_context + answer_template
│   │
│   │       templates.py
│   │           # Stores default templates and template loading logic.
│   │
│   │       variables.py
│   │           # Handles {{context}}, {{query}}, {{metadata}}, etc.
│   │
│   └── eval/
│           __init__.py
│           retrieval_eval.py
│               # Computes retrieval quality metrics (recall@k, MRR, etc.)
│
│           answer_eval.py
│               # Computes semantic similarity between model output and gold answers.
│
│           metrics.py
│               # Shared metric utilities.
│
│           goldset.py
│               # Loads and validates gold Q/A pairs for evaluation.
│
│
├── services/
│   │   rag_service.py
│   │       # The bridge between UI and backend.
│   │       # Exposes:
│   │       # - run_pipeline()
│   │       # - run_retrieval_test()
│   │       # - run_evaluation()
│   │       # - export_config()
│   │       # Uses rag.engine + adapters internally.
│   │
│   └── (existing services…)
│
│
├── ui/
│   │
│   ├── components/
│   │       rag_pipeline_editor.py
│   │           # UI for editing pipeline settings (chunker, embedder, retriever, etc.)
│   │
│   │       rag_prompt_editor.py
│   │           # UI for editing system/retrieval/answer templates.
│   │
│   │       rag_test_console.py
│   │           # UI for running test queries and showing:
│   │           # - retrieved chunks
│   │           # - distances
│   │           # - assembled prompt
│   │           # - model output
│   │
│   │       rag_eval_panel.py
│   │           # UI for gold Q/A evaluation and metrics display.
│   │
│   │       rag_export_panel.py
│   │           # UI for exporting Python/JS/YAML configs.
│   │
│   ├── dialogs/
│   │       rag_builder_dialog.py
│   │           # Optional: full-screen or modal RAG builder.
│   │
│   ├── views/
│   │       rag_builder_view.py
│   │           # Main RAG Builder tab/page in the app.
│   │
│   └── controllers/
│           rag_controller.py
│               # Connects UI → rag_service.
│               # Handles user actions, validation, and state updates.
│
│
├── state/
│   │   rag_state.py
│   │       # Holds all RAG builder state:
│   │       # - pipeline config
│   │       # - prompt templates
│   │       # - test query + results
│   │       # - evaluation results
│   │
│   │   rag_actions.py
│   │       # Functions that mutate state:
│   │       # - set_chunker_config()
│   │       # - set_embedder_config()
│   │       # - run_pipeline()
│   │       # - run_test()
│   │       # - run_eval()
│   │       # - export_config()
│   │
│   │   rag_selectors.py
│   │       # Derived state helpers:
│   │       # - get_current_pipeline()
│   │       # - get_prompt_preview()
│   │       # - get_eval_summary()
│   │
│   └── (existing state modules…)
│
│
└── utils/
        rag_serialization.py
            # YAML/JSON export helpers.
        rag_validation.py
            # Extra validation helpers for configs and templates.
        rag_textnorm.py
            # Optional text normalization utilities (strip whitespace, normalize unicode).
```