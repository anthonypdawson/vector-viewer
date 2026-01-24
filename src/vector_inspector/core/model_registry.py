"""Model registry for loading and managing known embedding models."""

import json
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class ModelInfo:
    """Information about an embedding model."""
    name: str
    type: str
    dimension: int
    modality: str
    normalization: str
    source: str
    description: str
    
    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "dimension": self.dimension,
            "modality": self.modality,
            "normalization": self.normalization,
            "source": self.source,
            "description": self.description
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ModelInfo':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            dimension=data["dimension"],
            modality=data["modality"],
            normalization=data["normalization"],
            source=data["source"],
            description=data["description"]
        )


class EmbeddingModelRegistry:
    """Registry of known embedding models loaded from JSON."""
    
    _instance = None
    _models: List[ModelInfo] = []
    _dimension_index: Dict[int, List[ModelInfo]] = {}
    _name_index: Dict[str, ModelInfo] = {}
    
    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_registry()
        return cls._instance
    
    def _load_registry(self):
        """Load models from JSON file."""
        registry_path = Path(__file__).parent.parent / "config" / "known_embedding_models.json"
        
        if not registry_path.exists():
            print(f"Warning: Model registry not found at {registry_path}")
            return

        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Parse models
            for model_data in data.get("models", []):
                model_info = ModelInfo.from_dict(model_data)
                self._models.append(model_info)
                
                # Index by dimension
                if model_info.dimension not in self._dimension_index:
                    self._dimension_index[model_info.dimension] = []
                self._dimension_index[model_info.dimension].append(model_info)
                
                # Index by name
                self._name_index[model_info.name.lower()] = model_info
            
            print(f"Loaded {len(self._models)} models from registry")
            #...
        except Exception as e:
            print(f"Error loading model registry: {e}")
    
    def get_models_by_dimension(self, dimension: int) -> List[ModelInfo]:
        """Get all models for a specific dimension.
        
        Args:
            dimension: Vector dimension
            
        Returns:
            List of ModelInfo objects
        """
        return self._dimension_index.get(dimension, [])
    
    def get_model_by_name(self, name: str) -> Optional[ModelInfo]:
        """Get model info by name (case-insensitive).
        
        Args:
            name: Model name
            
        Returns:
            ModelInfo or None if not found
        """
        return self._name_index.get(name.lower())
    
    def get_all_models(self) -> List[ModelInfo]:
        """Get all registered models.
        
        Returns:
            List of all ModelInfo objects
        """
        return self._models.copy()
    
    def get_all_dimensions(self) -> List[int]:
        """Get all available dimensions.
        
        Returns:
            Sorted list of dimensions
        """
        return sorted(self._dimension_index.keys())
    
    def find_closest_dimension(self, target_dimension: int) -> Optional[int]:
        """Find the closest available dimension.
        
        Args:
            target_dimension: Target dimension to match
            
        Returns:
            Closest dimension or None if no models exist
        """
        if not self._dimension_index:
            return None
        
        return min(self._dimension_index.keys(), key=lambda x: abs(x - target_dimension))
    
    def get_models_by_type(self, model_type: str) -> List[ModelInfo]:
        """Get all models of a specific type.
        
        Args:
            model_type: Model type (e.g., "sentence-transformer", "clip")
            
        Returns:
            List of ModelInfo objects
        """
        return [m for m in self._models if m.type == model_type]
    
    def get_models_by_source(self, source: str) -> List[ModelInfo]:
        """Get all models from a specific source.
        
        Args:
            source: Model source (e.g., "huggingface", "openai-api")
            
        Returns:
            List of ModelInfo objects
        """
        return [m for m in self._models if m.source == source]
    
    def search_models(self, query: str) -> List[ModelInfo]:
        """Search models by name or description.
        
        Args:
            query: Search query (case-insensitive)
            
        Returns:
            List of matching ModelInfo objects
        """
        query_lower = query.lower()
        results = []
        
        for model in self._models:
            if (query_lower in model.name.lower() or 
                query_lower in model.description.lower()):
                results.append(model)
        
        return results
    
    def reload(self):
        """Reload the registry from disk."""
        self._models.clear()
        self._dimension_index.clear()
        self._name_index.clear()
        self._load_registry()


# Global registry instance
_registry = None


def get_model_registry() -> EmbeddingModelRegistry:
    """Get the global model registry instance.
    
    Returns:
        EmbeddingModelRegistry singleton
    """
    global _registry
    if _registry is None:
        _registry = EmbeddingModelRegistry()
    return _registry
