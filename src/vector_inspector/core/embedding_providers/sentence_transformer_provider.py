"""Sentence Transformer embedding provider with lazy loading."""

from typing import List, Union, Optional
import numpy as np

from .base_provider import (
    EmbeddingProvider, 
    EmbeddingMetadata, 
    Modality, 
    Normalization
)


class SentenceTransformerProvider(EmbeddingProvider):
    """Provider for sentence-transformers models.
    
    Lazy-loads the sentence-transformers library and model on first use.
    Supports all models from the sentence-transformers library including:
    - all-MiniLM-L6-v2
    - all-mpnet-base-v2
    - BGE, GTE, E5 families
    - Multilingual variants
    """
    
    def __init__(self, model_name: str, trust_remote_code: bool = False):
        """Initialize sentence-transformer provider.
        
        Args:
            model_name: HuggingFace model ID or local path
            trust_remote_code: Whether to trust remote code (for some models)
        """
        super().__init__(model_name)
        self.trust_remote_code = trust_remote_code
        self._metadata = None
    
    def get_metadata(self) -> EmbeddingMetadata:
        """Get metadata about the sentence-transformer model.
        
        This attempts to extract metadata without loading the full model if possible.
        """
        if self._metadata is not None:
            return self._metadata
        
        # Try to get metadata without loading full model
        try:
            # Import config utilities
            from sentence_transformers import SentenceTransformer
            from transformers import AutoConfig
            
            # Try to get config without loading weights
            try:
                config = AutoConfig.from_pretrained(self.model_name)
                dimension = getattr(config, 'hidden_size', None)
                max_length = getattr(config, 'max_position_embeddings', None)
            except Exception:
                # If config fails, we'll need to load the model
                dimension = None
                max_length = None
            
            # If we couldn't get dimension from config, load model
            if dimension is None:
                if not self._is_loaded:
                    self._load_model()
                dimension = self._model.get_sentence_embedding_dimension()
                max_length = self._model.max_seq_length
            
            self._metadata = EmbeddingMetadata(
                name=self.model_name,
                dimension=int(dimension) if dimension is not None else 768,
                modality=Modality.TEXT,
                normalization=Normalization.L2,  # Most sentence-transformers normalize
                model_type="sentence-transformer",
                source="huggingface",
                max_sequence_length=max_length,
                description=f"Sentence-Transformer model: {self.model_name}"
            )
            
        except ImportError:
            # sentence-transformers not installed
            raise ImportError(
                "sentence-transformers library not installed. "
                "Install with: pip install sentence-transformers"
            )
        except Exception as e:
            # Fallback metadata if we can't determine dimension
            self._metadata = EmbeddingMetadata(
                name=self.model_name,
                dimension=768,  # Common default
                modality=Modality.TEXT,
                normalization=Normalization.L2,
                model_type="sentence-transformer",
                source="huggingface",
                description=f"Sentence-Transformer model: {self.model_name} (dimension not verified)"
            )
        
        return self._metadata
    
    def _load_model(self):
        """Load the sentence-transformer model."""
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError:
            raise ImportError(
                "sentence-transformers library not installed. "
                "Install with: pip install sentence-transformers"
            )
        
        # Load model with optional trust_remote_code
        self._model = SentenceTransformer(
            self.model_name,
            trust_remote_code=self.trust_remote_code
        )
    
    def encode(
        self,
        inputs: Union[str, List[str]],
        normalize: bool = True,
        show_progress: bool = False
    ) -> np.ndarray:
        """Encode text inputs into embeddings.
        
        Args:
            inputs: Single string or list of strings
            normalize: Whether to L2-normalize embeddings
            show_progress: Whether to show progress bar
            
        Returns:
            numpy array of embeddings
        """
        # Ensure model is loaded
        if not self._is_loaded:
            self.warmup()
        
        # Convert single string to list
        if isinstance(inputs, str):
            inputs = [inputs]
        
        # Encode
        embeddings = self._model.encode(
            inputs,
            normalize_embeddings=normalize,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def encode_batch(
        self,
        inputs: List[str],
        batch_size: int = 32,
        normalize: bool = True,
        show_progress: bool = True
    ) -> np.ndarray:
        """Encode a large batch of texts efficiently.
        
        Args:
            inputs: List of strings
            batch_size: Batch size for encoding
            normalize: Whether to L2-normalize embeddings
            show_progress: Whether to show progress bar
            
        Returns:
            numpy array of embeddings
        """
        if not self._is_loaded:
            self.warmup()
        
        embeddings = self._model.encode(
            inputs,
            batch_size=batch_size,
            normalize_embeddings=normalize,
            show_progress_bar=show_progress,
            convert_to_numpy=True
        )
        
        return embeddings
    
    def similarity(self, query: Union[str, np.ndarray], corpus: List[str]) -> np.ndarray:
        """Compute similarity between query and corpus.
        
        Args:
            query: Query string or embedding
            corpus: List of corpus strings
            
        Returns:
            Similarity scores (cosine similarity if normalized)
        """
        if not self._is_loaded:
            self.warmup()
        
        # Get embeddings
        if isinstance(query, str):
            query_emb = self.encode(query, normalize=True)
        else:
            query_emb = query
        
        corpus_emb = self.encode(corpus, normalize=True)
        
        # Compute cosine similarity (dot product if normalized)
        similarities = np.dot(corpus_emb, query_emb.T).squeeze()
        
        return similarities
