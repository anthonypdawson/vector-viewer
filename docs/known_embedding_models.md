# Known Embedding Models (Registry)

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

---

Contributing

- When adding a new model, include a short reasoning for choosing it and any special preprocessing rules (e.g., lowercasing, tokenization differences).
- Eventually we should move this registry to a JSON file under `src/` and expose a UI to extend it at runtime.
