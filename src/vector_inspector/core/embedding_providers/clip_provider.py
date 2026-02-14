"""CLIP embedding provider for multimodal (text + image) embeddings."""

from pathlib import Path
from typing import Any

import numpy as np

from .base_provider import EmbeddingMetadata, EmbeddingProvider, Modality, Normalization


class CLIPProvider(EmbeddingProvider):
    """Provider for CLIP models supporting text and image embeddings.

    Lazy-loads the transformers library and CLIP model on first use.
    Supports OpenAI CLIP and LAION CLIP variants:
    - openai/clip-vit-base-patch32
    - openai/clip-vit-large-patch14
    - laion/CLIP-ViT-B-32-laion2B-s34B-b79K
    - And other CLIP-compatible models
    """

    def __init__(self, model_name: str):
        """Initialize CLIP provider.

        Args:
            model_name: HuggingFace model ID (e.g., "openai/clip-vit-base-patch32")
        """
        super().__init__(model_name)
        self._processor = None
        self._metadata = None

    def get_metadata(self) -> EmbeddingMetadata:
        """Get metadata about the CLIP model."""
        if self._metadata is not None:
            return self._metadata

        try:
            from transformers import CLIPConfig

            # Try to get config without loading full model
            try:
                config = CLIPConfig.from_pretrained(self.model_name)
                dimension = config.projection_dim
                max_length = config.text_config.max_position_embeddings
            except Exception:
                # Fallback dimensions for common CLIP models
                dimension_map = {
                    "openai/clip-vit-base-patch32": 512,
                    "openai/clip-vit-base-patch16": 512,
                    "openai/clip-vit-large-patch14": 768,
                    "openai/clip-vit-large-patch14-336": 768,
                }
                dimension = dimension_map.get(self.model_name, 512)
                max_length = 77  # Standard CLIP text length

            self._metadata = EmbeddingMetadata(
                name=self.model_name,
                dimension=dimension,
                modality=Modality.MULTIMODAL,
                normalization=Normalization.L2,  # CLIP normalizes embeddings
                model_type="clip",
                source="huggingface",
                max_sequence_length=max_length,
                description=f"CLIP multimodal model: {self.model_name}",
            )

        except ImportError:
            raise ImportError(
                "transformers library not installed. Install with: pip install transformers"
            )
        except Exception:
            # Fallback metadata
            self._metadata = EmbeddingMetadata(
                name=self.model_name,
                dimension=512,  # Common CLIP dimension
                modality=Modality.MULTIMODAL,
                normalization=Normalization.L2,
                model_type="clip",
                source="huggingface",
                description=f"CLIP model: {self.model_name} (dimension not verified)",
            )

        return self._metadata

    def _load_model(self):
        """Load the CLIP model and processor."""
        try:
            from transformers.models.clip import CLIPModel, CLIPProcessor
        except ImportError:
            raise ImportError(
                "transformers library not installed or CLIP modules missing. Install with: pip install transformers"
            )

        # Try to load from cache first
        from vector_inspector.core.logging import log_info
        from vector_inspector.core.model_cache import (
            is_cache_enabled,
            load_cached_path,
            save_model_to_cache,
        )

        cached_path = load_cached_path(self.model_name)

        if cached_path:
            try:
                # Load from cache
                self._model = CLIPModel.from_pretrained(str(cached_path))
                processor_path = cached_path / "processor"
                if processor_path.exists():
                    self._processor = CLIPProcessor.from_pretrained(str(processor_path))
                else:
                    # Fallback: load processor from original model name
                    self._processor = CLIPProcessor.from_pretrained(self.model_name)
                log_info(f"Loaded CLIP model from cache: {self.model_name}")

                # Move to GPU if available
                try:
                    import torch

                    if torch.cuda.is_available():
                        self._model = self._model.to("cuda")
                except ImportError:
                    pass  # PyTorch not available, stay on CPU
                return
            except Exception as e:
                log_info(f"Failed to load from cache, downloading: {e}")

        # Load from HuggingFace
        self._model = CLIPModel.from_pretrained(self.model_name)
        self._processor = CLIPProcessor.from_pretrained(self.model_name)

        # Move to GPU if available
        try:
            import torch

            if torch.cuda.is_available():
                self._model = self._model.to("cuda")
        except ImportError:
            pass  # PyTorch not available, stay on CPU

        # Cache for future use
        if is_cache_enabled():
            save_model_to_cache((self._model, self._processor), self.model_name, "clip")

    def encode(
        self,
        inputs: str | list[str] | Any,
        normalize: bool = True,
        show_progress: bool = False,
        input_type: str = "text",
    ) -> np.ndarray:
        """Encode text or images into embeddings.

        Args:
            inputs: Text strings, image paths, or PIL images
            normalize: Whether to L2-normalize embeddings
            show_progress: Whether to show progress (not implemented for CLIP)
            input_type: "text" or "image"

        Returns:
            numpy array of embeddings
        """
        if not self._is_loaded:
            self.warmup()

        try:
            import torch
        except ImportError:
            raise ImportError("PyTorch required for CLIP. Install with: pip install torch")

        # Convert single input to list
        if isinstance(inputs, str) or not isinstance(inputs, list):
            inputs = [inputs]

        if self._processor is None:
            raise RuntimeError("Model not loaded. Call warmup() first.")

        with torch.no_grad():
            if input_type == "text":
                # Process text
                processed = self._processor(
                    text=inputs, return_tensors="pt", padding=True, truncation=True
                )

                # Move to same device as model
                if next(self._model.parameters()).is_cuda:
                    processed = {k: v.cuda() for k, v in processed.items()}

                # Get text embeddings
                embeddings = self._model.get_text_features(**processed)

            elif input_type == "image":
                # Load images if they're paths
                images = []
                for inp in inputs:
                    if isinstance(inp, (str, Path)):
                        from PIL import Image

                        images.append(Image.open(inp))
                    else:
                        images.append(inp)  # Assume already PIL Image

                # Process images
                processed = self._processor(images=images, return_tensors="pt")

                # Move to same device as model
                if next(self._model.parameters()).is_cuda:
                    processed = {k: v.cuda() for k, v in processed.items()}

                # Get image embeddings
                embeddings = self._model.get_image_features(**processed)
            else:
                raise ValueError(f"Unknown input_type: {input_type}. Use 'text' or 'image'")

            # Convert to numpy
            embeddings = embeddings.cpu().numpy()

            # Normalize if requested (CLIP typically normalizes, but we can ensure it)
            if normalize:
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                embeddings = embeddings / norms

        return embeddings

    def encode_text(self, texts: str | list[str], normalize: bool = True) -> np.ndarray:
        """Encode text inputs into embeddings.

        Args:
            texts: Single text or list of texts
            normalize: Whether to L2-normalize

        Returns:
            numpy array of text embeddings
        """
        return self.encode(texts, normalize=normalize, input_type="text")

    def encode_image(self, images: str | Path | Any | list, normalize: bool = True) -> np.ndarray:
        """Encode images into embeddings.

        Args:
            images: Image path(s) or PIL Image(s)
            normalize: Whether to L2-normalize

        Returns:
            numpy array of image embeddings
        """
        return self.encode(images, normalize=normalize, input_type="image")

    def similarity(
        self,
        query: str | np.ndarray,
        corpus: list[str],
        query_type: str = "text",
        corpus_type: str = "text",
    ) -> np.ndarray:
        """Compute similarity between query and corpus (text or image).

        Args:
            query: Query string/image or embedding
            corpus: List of corpus items (text or images)
            query_type: "text" or "image"
            corpus_type: "text" or "image"

        Returns:
            Similarity scores (cosine similarity)
        """
        if not self._is_loaded:
            self.warmup()

        # Get embeddings
        if isinstance(query, np.ndarray):
            query_emb = query
        else:
            query_emb = self.encode(query, normalize=True, input_type=query_type)

        corpus_emb = self.encode(corpus, normalize=True, input_type=corpus_type)

        # Compute cosine similarity (dot product if normalized)
        similarities = np.dot(corpus_emb, query_emb.T).squeeze()

        return similarities
