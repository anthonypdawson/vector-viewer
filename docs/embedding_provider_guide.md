# Embedding Provider System - Developer Guide

## Overview

The Embedding Provider system provides a unified, pluggable interface for loading and using embedding models from various sources (HuggingFace, local files, cloud APIs). It implements lazy-loading to prevent UI freezes and provides consistent metadata extraction across different model types.

## Architecture

### Core Components

1. **EmbeddingProvider (Base Class)** - Abstract interface all providers must implement
2. **SentenceTransformerProvider** - Handles sentence-transformers models
3. **CLIPProvider** - Handles multimodal (text + image) CLIP models
4. **ProviderFactory** - Creates appropriate provider instances with auto-detection

### Key Features

- **Lazy Loading**: Models are loaded on first use, not at initialization
- **Metadata Extraction**: Dimension, modality, normalization info without loading full model
- **Context Manager Support**: Automatic cleanup with `with` statements
- **Auto-detection**: Intelligently determines provider type from model name
- **Progress Callbacks**: Support for UI progress updates during model loading

## Usage

### Basic Usage

```python
from vector_inspector.core.embedding_providers import create_provider

# Create provider (auto-detects type)
provider = create_provider("all-MiniLM-L6-v2")

# Get metadata (fast, no model loading)
metadata = provider.get_metadata()
print(f"Dimension: {metadata.dimension}")

# Encode text (lazy-loads model on first call)
embeddings = provider.encode(["Hello world", "Goodbye world"])

# Cleanup
provider.close()
```

### Context Manager

```python
with create_provider("all-mpnet-base-v2") as provider:
    embeddings = provider.encode(texts)
    # Model automatically cleaned up
```

### Explicit Provider Type

```python
# Specify type explicitly
provider = create_provider(
    "openai/clip-vit-base-patch32",
    model_type="clip"
)
```

### CLIP Multimodal Usage

```python
from vector_inspector.core.embedding_providers import CLIPProvider

provider = CLIPProvider("openai/clip-vit-base-patch32")

# Encode text
text_embeddings = provider.encode_text(["a cat", "a dog"])

# Encode images
image_embeddings = provider.encode_image(["cat.jpg", "dog.jpg"])

# Cross-modal similarity
similarity = provider.similarity(
    "a photo of a cat",
    ["cat.jpg", "dog.jpg"],
    query_type="text",
    corpus_type="image"
)
```

### Progress Callback for UI

```python
def progress_callback(message, progress):
    """Update UI with loading progress."""
    print(f"{message} ({progress*100:.0f}%)")

provider = create_provider("BAAI/bge-large-en-v1.5")
provider.warmup(progress_callback=progress_callback)
```

## Provider Types

### Currently Implemented

| Type | Provider Class | Models Supported |
|------|---------------|------------------|
| `sentence-transformer` | `SentenceTransformerProvider` | All sentence-transformers models (MiniLM, MPNet, BGE, GTE, E5, etc.) |
| `clip` | `CLIPProvider` | OpenAI CLIP, LAION CLIP variants |

### Coming Soon

- `openai` - OpenAI embedding API (text-embedding-3-small/large)
- `cohere` - Cohere embed models
- `vertex-ai` - Google Vertex AI embeddings
- `voyage` - Voyage AI embeddings

## Metadata Structure

```python
@dataclass
class EmbeddingMetadata:
    name: str                    # Model identifier
    dimension: int               # Vector dimension
    modality: Modality          # TEXT, IMAGE, or MULTIMODAL
    normalization: Normalization # NONE or L2
    model_type: str             # Provider type
    source: str                 # huggingface, local, cloud, etc.
    version: Optional[str]      # Model version
    max_sequence_length: Optional[int]  # Max input length
    description: Optional[str]  # Human-readable description
```

## Integration with Settings

The provider system integrates with `SettingsService` for persistent model choices:

```python
from vector_inspector.services.settings_service import SettingsService
from vector_inspector.core.embedding_providers import create_provider

settings = SettingsService()

# Save model choice for a collection
connection_id = "my_chromadb"
collection_name = "documents"
provider = create_provider("all-MiniLM-L6-v2")
metadata = provider.get_metadata()

settings.save_embedding_model(
    connection_id,
    collection_name,
    metadata.name,
    metadata.model_type
)

# Later, retrieve and recreate provider
model_info = settings.get_embedding_model(connection_id, collection_name)
if model_info:
    provider = create_provider(
        model_info['model'],
        model_type=model_info['type']
    )
```

## Adding New Providers

### 1. Create Provider Class

```python
from .base_provider import EmbeddingProvider, EmbeddingMetadata

class MyCustomProvider(EmbeddingProvider):
    def get_metadata(self) -> EmbeddingMetadata:
        # Return metadata
        pass
    
    def _load_model(self):
        # Load model implementation
        pass
    
    def encode(self, inputs, normalize=True, show_progress=False):
        # Encoding implementation
        pass
```

### 2. Register with Factory

```python
from vector_inspector.core.embedding_providers import ProviderFactory

ProviderFactory.register_provider("my-type", MyCustomProvider)
```

### 3. Add Auto-detection Patterns (Optional)

Edit `provider_factory.py` to add model name patterns for auto-detection.

## Model Registry

Known models are stored in a JSON file at `src/vector_inspector/config/known_embedding_models.json`. This registry is loaded at runtime and provides:

- **47+ pre-configured models** across all major providers
- **Auto-detection** of provider type from model name
- **Metadata** for dimension, modality, normalization, and source
- **Search and filtering** by dimension, type, or source

The registry is accessed through the `EmbeddingModelRegistry` class:

```python
from vector_inspector.core.model_registry import get_model_registry

registry = get_model_registry()

# Get models for a specific dimension
models_384d = registry.get_models_by_dimension(384)

# Look up specific model
model_info = registry.get_model_by_name("all-MiniLM-L6-v2")
print(f"Dimension: {model_info.dimension}, Type: {model_info.type}")

# Search models
clip_models = registry.search_models("clip")

# Filter by type
sentence_transformers = registry.get_models_by_type("sentence-transformer")
```

### Adding Models to Registry

For new releases, edit `known_embedding_models.json`:

```json
{
  "name": "your-model-name",
  "type": "sentence-transformer",
  "dimension": 768,
  "modality": "text",
  "normalization": "l2",
  "source": "huggingface",
  "description": "Your model description"
}
```

User-added custom models are stored separately in their settings file and are automatically combined with the registry models at runtime.

The markdown documentation at [known_embedding_models.md](known_embedding_models.md) is maintained for reference, but the JSON file is the authoritative source.

## Performance Considerations

### Lazy Loading Benefits

- **No upfront cost**: Models only loaded when actually needed
- **UI responsiveness**: Dialog can show metadata instantly
- **Memory efficiency**: Unused models don't consume memory

### Caching Strategy

Current implementation keeps one model loaded per provider instance. Future enhancements:

- Global model cache to share across provider instances
- LRU eviction for memory management
- Persistent disk cache for faster subsequent loads

### GPU Support

Both providers automatically use GPU if available:

```python
# SentenceTransformerProvider: Uses device auto-detection
# CLIPProvider: Moves to CUDA if torch.cuda.is_available()
```

## Testing

Run the example script to test all provider functionality:

```bash
python test_scripts/test_embedding_providers.py
```

This demonstrates:
- Auto-detection
- Metadata extraction
- Encoding
- Similarity computation
- Context manager usage
- Custom model handling

## Troubleshooting

### ImportError: sentence-transformers not installed

```bash
pip install sentence-transformers
```

### ImportError: transformers not installed

```bash
pip install transformers torch pillow
```

### Model not loading

Check that the model name is correct and accessible from HuggingFace or local path.

### Dimension mismatch

If provider.metadata.dimension doesn't match collection dimension, the model may be wrong. Use the UI validation button to verify before saving.

## Future Enhancements

- [ ] Cloud API providers (OpenAI, Cohere, etc.)
- [ ] Global model cache with LRU eviction
- [ ] Async loading with async/await
- [ ] Model quantization support
- [ ] ONNX runtime provider for faster inference
- [ ] Batch processing optimizations
- [ ] Credential management for cloud APIs
