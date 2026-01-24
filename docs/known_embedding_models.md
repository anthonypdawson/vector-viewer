# Known Embedding Models (Registry)

> **Note:** This document is maintained for reference. The authoritative source is the JSON registry at:
> `src/vector_inspector/config/known_embedding_models.json`
>
> The JSON file is loaded at runtime and combined with user-added custom models to provide
> the complete model catalog. When adding new models for releases, update the JSON file.

This file is a living registry of embedding models the app is aware of. Each entry includes the model identifier we use, the source/type, vector dimension, modality, and a short description. As we discover new models or variants, add them here.

## Format
- Model: human-friendly name or HF id
- Type: `sentence-transformer` | `clip` | `hf-generic` | `custom`
- Dimension: integer (vector size)
- Modality: `text` | `image` | `multimodal`
- Normalization: `l2` | `none` (recommended)
- Notes: additional info

---

### all-MiniLM-L6-v2
- Model: `all-MiniLM-L6-v2`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2 (recommended)
- Notes: Fast, small-footprint text embeddings (good default for text search).

### openai/clip-vit-base-patch32
- Model: `openai/clip-vit-base-patch32`
- Type: `clip`
- Dimension: 512
- Modality: multimodal (text + image)
- Normalization: l2 (CLIP typically uses normalized vectors)
- Notes: Standard CLIP ViT-B/32 model; supports matching text ↔ images.

### paraphrase-albert-small-v2
- Model: `paraphrase-albert-small-v2`
- Type: `sentence-transformer`
- Dimension: 512
- Modality: text
- Normalization: l2
- Notes: Smaller paraphrase-specialized model useful where 512-d vectors exist.

### all-mpnet-base-v2
- Model: `all-mpnet-base-v2`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: High-quality text embeddings; recommended for semantic tasks when size allows.

### all-roberta-large-v1
- Model: `all-roberta-large-v1`
- Type: `sentence-transformer`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: Large model — high quality, larger memory and compute.

### gtr-t5-large
- Model: `gtr-t5-large`
- Type: `sentence-transformer`
- Dimension: 1536
- Modality: text
- Normalization: l2
- Notes: Very large embeddings useful for specialized high-recall tasks.

### sentence-transformers/multi-qa-MiniLM-L6-cos-v1
- Model: `sentence-transformers/multi-qa-MiniLM-L6-cos-v1`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: Optimized for semantic search and question-answering tasks.

### sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
- Model: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: Multilingual support for 50+ languages.

### sentence-transformers/msmarco-distilbert-base-v4
- Model: `sentence-transformers/msmarco-distilbert-base-v4`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Trained on MS MARCO dataset, good for passage retrieval.

### sentence-transformers/all-distilroberta-v1
- Model: `sentence-transformers/all-distilroberta-v1`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Distilled RoBERTa model, balance of speed and quality.

### sentence-transformers/paraphrase-mpnet-base-v2
- Model: `sentence-transformers/paraphrase-mpnet-base-v2`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: High-quality paraphrase detection and semantic similarity.

### BAAI/bge-small-en-v1.5
- Model: `BAAI/bge-small-en-v1.5`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: Beijing Academy of AI model, strong performance for size.

### BAAI/bge-base-en-v1.5
- Model: `BAAI/bge-base-en-v1.5`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: High-quality English embeddings, MTEB benchmark leader.

### BAAI/bge-large-en-v1.5
- Model: `BAAI/bge-large-en-v1.5`
- Type: `sentence-transformer`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: Large model with excellent retrieval performance.

### thenlper/gte-small
- Model: `thenlper/gte-small`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: General Text Embeddings (GTE) small variant.

### thenlper/gte-base
- Model: `thenlper/gte-base`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: General Text Embeddings (GTE) base model.

### thenlper/gte-large
- Model: `thenlper/gte-large`
- Type: `sentence-transformer`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: General Text Embeddings (GTE) large variant.

### intfloat/e5-small-v2
- Model: `intfloat/e5-small-v2`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: E5 family small model, prefix with "query: " or "passage: ".

### intfloat/e5-base-v2
- Model: `intfloat/e5-base-v2`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: E5 family base model, strong asymmetric retrieval.

### intfloat/e5-large-v2
- Model: `intfloat/e5-large-v2`
- Type: `sentence-transformer`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: E5 family large model, top MTEB performance.

### intfloat/multilingual-e5-small
- Model: `intfloat/multilingual-e5-small`
- Type: `sentence-transformer`
- Dimension: 384
- Modality: text
- Normalization: l2
- Notes: Multilingual E5 model supporting 100+ languages.

### intfloat/multilingual-e5-base
- Model: `intfloat/multilingual-e5-base`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Multilingual E5 base model, excellent cross-lingual retrieval.

### intfloat/multilingual-e5-large
- Model: `intfloat/multilingual-e5-large`
- Type: `sentence-transformer`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: Multilingual E5 large model, best-in-class multilingual embeddings.

---

## CLIP Models (Multimodal)

### openai/clip-vit-large-patch14
- Model: `openai/clip-vit-large-patch14`
- Type: `clip`
- Dimension: 768
- Modality: multimodal (text + image)
- Normalization: l2
- Notes: Larger CLIP ViT-L/14 model, better quality than base.

### openai/clip-vit-large-patch14-336
- Model: `openai/clip-vit-large-patch14-336`
- Type: `clip`
- Dimension: 768
- Modality: multimodal (text + image)
- Normalization: l2
- Notes: Higher resolution (336x336) variant of ViT-L/14.

### laion/CLIP-ViT-B-32-laion2B-s34B-b79K
- Model: `laion/CLIP-ViT-B-32-laion2B-s34B-b79K`
- Type: `clip`
- Dimension: 512
- Modality: multimodal (text + image)
- Normalization: l2
- Notes: LAION's CLIP trained on 2B image-text pairs.

### laion/CLIP-ViT-H-14-laion2B-s32B-b79K
- Model: `laion/CLIP-ViT-H-14-laion2B-s32B-b79K`
- Type: `clip`
- Dimension: 1024
- Modality: multimodal (text + image)
- Normalization: l2
- Notes: LAION's huge CLIP model, excellent quality.

---

## OpenAI Cloud Models

### text-embedding-ada-002
- Model: `text-embedding-ada-002`
- Type: `openai`
- Dimension: 1536
- Modality: text
- Normalization: l2 (OpenAI normalizes by default)
- Notes: OpenAI's production embedding model (legacy). Requires API key.

### text-embedding-3-small
- Model: `text-embedding-3-small`
- Type: `openai`
- Dimension: 1536
- Modality: text
- Normalization: l2
- Notes: OpenAI's newer small model, better than ada-002. Requires API key.

### text-embedding-3-large
- Model: `text-embedding-3-large`
- Type: `openai`
- Dimension: 3072
- Modality: text
- Normalization: l2
- Notes: OpenAI's large embedding model, highest quality. Requires API key. Can be dimensionally reduced (256-3072).

---

## Cohere Cloud Models

### embed-english-v3.0
- Model: `embed-english-v3.0`
- Type: `cohere`
- Dimension: 1024
- Modality: text
- Normalization: none (depends on input_type)
- Notes: Cohere's English embedding model. Requires API key. Supports input_type parameter.

### embed-english-light-v3.0
- Model: `embed-english-light-v3.0`
- Type: `cohere`
- Dimension: 384
- Modality: text
- Normalization: none
- Notes: Cohere's lightweight English model. Requires API key.

### embed-multilingual-v3.0
- Model: `embed-multilingual-v3.0`
- Type: `cohere`
- Dimension: 1024
- Modality: text
- Normalization: none
- Notes: Cohere's multilingual model supporting 100+ languages. Requires API key.

### embed-multilingual-light-v3.0
- Model: `embed-multilingual-light-v3.0`
- Type: `cohere`
- Dimension: 384
- Modality: text
- Normalization: none
- Notes: Cohere's lightweight multilingual model. Requires API key.

---

## Google Cloud Models (Vertex AI)

### textembedding-gecko@003
- Model: `textembedding-gecko@003`
- Type: `vertex-ai`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Google's Gecko model for text embeddings. Requires Google Cloud credentials.

### text-embedding-004
- Model: `text-embedding-004`
- Type: `vertex-ai`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Google's latest text embedding model. Requires Google Cloud credentials.

### text-multilingual-embedding-002
- Model: `text-multilingual-embedding-002`
- Type: `vertex-ai`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Google's multilingual embedding model. Requires Google Cloud credentials.

### multimodalembedding@001
- Model: `multimodalembedding@001`
- Type: `vertex-ai`
- Dimension: 1408
- Modality: multimodal (text + image + video)
- Normalization: l2
- Notes: Google's multimodal embedding model. Requires Google Cloud credentials.

---

## Voyage AI Cloud Models

### voyage-large-2
- Model: `voyage-large-2`
- Type: `voyage`
- Dimension: 1536
- Modality: text
- Normalization: l2
- Notes: Voyage AI's large model. Requires API key.

### voyage-code-2
- Model: `voyage-code-2`
- Type: `voyage`
- Dimension: 1536
- Modality: text
- Normalization: l2
- Notes: Voyage AI's code-optimized model. Requires API key.

### voyage-2
- Model: `voyage-2`
- Type: `voyage`
- Dimension: 1024
- Modality: text
- Normalization: l2
- Notes: Voyage AI's general-purpose model. Requires API key.

---

## Specialized Models

### jinaai/jina-embeddings-v2-base-en
- Model: `jinaai/jina-embeddings-v2-base-en`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Jina AI's 8k context length model, good for long documents.

### jinaai/jina-embeddings-v2-small-en
- Model: `jinaai/jina-embeddings-v2-small-en`
- Type: `sentence-transformer`
- Dimension: 512
- Modality: text
- Normalization: l2
- Notes: Jina AI's small model with 8k context length.

### nomic-ai/nomic-embed-text-v1
- Model: `nomic-ai/nomic-embed-text-v1`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Nomic's open-source text embedding model with 8k context.

### nomic-ai/nomic-embed-text-v1.5
- Model: `nomic-ai/nomic-embed-text-v1.5`
- Type: `sentence-transformer`
- Dimension: 768
- Modality: text
- Normalization: l2
- Notes: Nomic's improved model with better performance.

### Alibaba-NLP/gte-Qwen2-7B-instruct
- Model: `Alibaba-NLP/gte-Qwen2-7B-instruct`
- Type: `sentence-transformer`
- Dimension: 3584
- Modality: text
- Normalization: l2
- Notes: Very large instruction-following embedding model, SOTA on many benchmarks.

### nvidia/NV-Embed-v1
- Model: `nvidia/NV-Embed-v1`
- Type: `sentence-transformer`
- Dimension: 4096
- Modality: text
- Normalization: l2
- Notes: NVIDIA's embedding model, excellent for retrieval tasks.

---

## Contributing

- **To add a new model for a release:** Edit `src/vector_inspector/config/known_embedding_models.json`
- Include: name, type, dimension, modality, normalization, source, and description
- For cloud models, note API key/credential requirement in the description
- Update this markdown file to keep documentation in sync
- Users can also add custom models at runtime through the UI, which are stored separately in their settings
