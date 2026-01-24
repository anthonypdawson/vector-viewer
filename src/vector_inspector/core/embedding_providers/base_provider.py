"""Base interface for embedding providers."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Union, Optional, Any
from enum import Enum
import numpy as np


class Modality(Enum):
    """Embedding modality types."""
    TEXT = "text"
    IMAGE = "image"
    MULTIMODAL = "multimodal"


class Normalization(Enum):
    """Embedding normalization types."""
    NONE = "none"
    L2 = "l2"


@dataclass
class EmbeddingMetadata:
    """Metadata about an embedding model."""
    name: str  # Model identifier (e.g., "all-MiniLM-L6-v2")
    dimension: int  # Vector dimension
    modality: Modality  # text, image, or multimodal
    normalization: Normalization  # none or l2
    model_type: str  # sentence-transformer, clip, openai, etc.
    source: str = "unknown"  # hf, local, custom, cloud
    version: Optional[str] = None  # Model version if available
    max_sequence_length: Optional[int] = None  # Maximum input length
    description: Optional[str] = None  # Human-readable description


class EmbeddingProvider(ABC):
    """Abstract base class for embedding providers.
    
    Providers handle loading, encoding, and metadata extraction for embedding models.
    They implement lazy-loading to avoid UI freezes when working with large models.
    """
    
    def __init__(self, model_name: str):
        """Initialize provider with a model name.
        
        Args:
            model_name: Model identifier (HuggingFace ID, path, or API model name)
        """
        self.model_name = model_name
        self._model = None  # Lazy-loaded model instance
        self._is_loaded = False
        
    @abstractmethod
    def get_metadata(self) -> EmbeddingMetadata:
        """Get metadata about the embedding model.
        
        This should be fast and not require loading the full model if possible.
        
        Returns:
            EmbeddingMetadata with model information
        """
        pass
    
    @abstractmethod
    def encode(
        self, 
        inputs: Union[str, List[str], Any],
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """Encode inputs into embeddings.
        
        Args:
            inputs: Text strings, images, or other inputs depending on modality
            normalize: Whether to L2-normalize the embeddings
            show_progress: Whether to show progress bar for batch encoding
            
        Returns:
            numpy array of embeddings, shape (n_inputs, dimension)
        """
        pass
    
    def warmup(self, progress_callback=None):
        """Load and initialize the model (warm up for faster subsequent calls).
        
        Args:
            progress_callback: Optional callback(message: str, progress: float) for UI updates
        """
        if self._is_loaded:
            return
            
        if progress_callback:
            progress_callback(f"Loading {self.model_name}...", 0.0)
        
        self._load_model()
        self._is_loaded = True
        
        if progress_callback:
            progress_callback(f"Model {self.model_name} loaded", 1.0)
    
    @abstractmethod
    def _load_model(self):
        """Internal method to load the actual model. Override in subclasses."""
        pass
    
    def close(self):
        """Release model resources and cleanup."""
        if self._model is not None:
            # Try to free memory
            del self._model
            self._model = None
            self._is_loaded = False
    
    @property
    def is_loaded(self) -> bool:
        """Check if model is currently loaded in memory."""
        return self._is_loaded
    
    def __enter__(self):
        """Context manager support."""
        self.warmup()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager cleanup."""
        self.close()
        return False
