"""Model registry for loading and managing known embedding models."""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from vector_inspector.core.logging import log_error, log_info


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

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "type": self.type,
            "dimension": self.dimension,
            "modality": self.modality,
            "normalization": self.normalization,
            "source": self.source,
            "description": self.description,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModelInfo":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            type=data["type"],
            dimension=data["dimension"],
            modality=data["modality"],
            normalization=data["normalization"],
            source=data["source"],
            description=data["description"],
        )


class EmbeddingModelRegistry:
    """Registry of known embedding models loaded from JSON.

    Uses singleton pattern to ensure only one instance exists, preventing state inconsistencies
    when code creates instances directly vs using AppState.
    """

    _instance: Optional["EmbeddingModelRegistry"] = None

    def __new__(cls):
        """Ensure only one instance exists (singleton pattern)."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize and load the model registry (only runs once due to singleton)."""
        # Skip if already initialized (check instance dict only, not class dict)
        if "_initialized" in self.__dict__:
            return
        self._initialized = True

        self._models: list[ModelInfo] = []
        self._dimension_index: dict[int, list[ModelInfo]] = {}
        self._name_index: dict[str, ModelInfo] = {}
        self._load_registry()

    def _load_registry(self):
        """Load models from JSON file."""
        registry_path = Path(__file__).parent.parent / "config" / "known_embedding_models.json"

        if not registry_path.exists():
            log_info("Warning: Model registry not found at %s", registry_path)
            return

        try:
            with open(registry_path, encoding="utf-8") as f:
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

            log_info("Loaded %d models from registry", len(self._models))
            # ...
        except Exception as e:
            log_error("Error loading model registry: %s", e)

    def get_models_by_dimension(self, dimension: int) -> list[ModelInfo]:
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

    def get_all_models(self) -> list[ModelInfo]:
        """Get all registered models.

        Returns:
            List of all ModelInfo objects
        """
        return self._models.copy()

    def get_all_dimensions(self) -> list[int]:
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

    def get_models_by_type(self, model_type: str) -> list[ModelInfo]:
        """Get all models of a specific type.

        Args:
            model_type: Model type (e.g., "sentence-transformer", "clip")

        Returns:
            List of ModelInfo objects
        """
        return [m for m in self._models if m.type == model_type]

    def get_models_by_source(self, source: str) -> list[ModelInfo]:
        """Get all models from a specific source.

        Args:
            source: Model source (e.g., "huggingface", "openai-api")

        Returns:
            List of ModelInfo objects
        """
        return [m for m in self._models if m.source == source]

    def search_models(self, query: str) -> list[ModelInfo]:
        """Search models by name or description.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching ModelInfo objects
        """
        query_lower = query.lower()
        results = []

        for model in self._models:
            if query_lower in model.name.lower() or query_lower in model.description.lower():
                results.append(model)

        return results

    def reload(self):
        """Reload the registry from disk."""
        self._models.clear()
        self._dimension_index.clear()
        self._name_index.clear()
        self._load_registry()


# Legacy global function for backward compatibility
# DEPRECATED: New code should use app_state.model_registry instead
def get_model_registry() -> EmbeddingModelRegistry:
    """Get the singleton model registry instance.

    DEPRECATED: This returns the singleton instance for legacy code.
    New code should use app_state.model_registry instead.

    Note: EmbeddingModelRegistry uses singleton pattern, so this always returns
    the same instance that AppState uses.
    """
    return EmbeddingModelRegistry()
