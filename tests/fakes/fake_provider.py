"""In-memory FakeProvider for unit tests.

Provides a lightweight VectorDBConnection-like API used by tests.
This implementation is intended only for tests and lives under tests/fakes.
"""

import uuid
from typing import Any, Optional

import numpy as np


class FakeProvider:
    def __init__(self, collections: Optional[dict[str, dict[str, Any]]] = None):
        # collections: name -> {ids: [], documents: [], metadatas: [], embeddings: []}
        self._collections = collections or {}
        self._connected = True

    def _ensure_collection(self, name: str):
        if name not in self._collections:
            self._collections[name] = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "embeddings": [],
            }

    def _matches_where(
        self, meta: Optional[dict[str, Any]], where: Optional[dict[str, Any]]
    ) -> bool:
        if not where:
            return True
        if meta is None:
            return False
        return all(meta.get(k) == v for k, v in where.items())

    def connect(self) -> bool:
        self._connected = True
        return True

    def disconnect(self):
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def list_collections(self) -> list[str]:
        return list(self._collections.keys())

    def get_collection_info(self, name: str) -> Optional[dict[str, Any]]:
        if name not in self._collections:
            return None
        col = self._collections[name]
        return {
            "name": name,
            "count": len(col.get("ids", [])),
            "metadata_fields": list(
                {k for m in col.get("metadatas", []) for k in (m or {}).keys()}
            ),
        }

    # Alias used by some code paths
    def get_collection_stats(self, name: str) -> Optional[dict[str, Any]]:
        return self.get_collection_info(name)

    def create_collection(
        self,
        name: str,
        docs_or_dimension: Optional[Any] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
        embeddings: Optional[list[list[float]]] = None,
        ids: Optional[list[str]] = None,
    ):
        """Create a collection. Supports two signatures:
        1. create_collection(name, vector_dimension: int) - used by BackupRestoreService
        2. create_collection(name, docs, metadatas, embeddings, ids) - test-friendly
        """
        # Check if this is the real provider signature (name, vector_dimension)
        if isinstance(docs_or_dimension, int) or docs_or_dimension is None:
            # Provider signature: just create empty collection
            self._collections[name] = {
                "ids": [],
                "documents": [],
                "metadatas": [],
                "embeddings": [],
            }
            return True

        # Test-friendly signature with docs list
        docs = docs_or_dimension or []
        metadatas = metadatas or [None] * len(docs)
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in docs]
        embeddings = embeddings or [None] * len(docs)
        self._collections[name] = {
            "ids": ids,
            "documents": docs,
            "metadatas": metadatas,
            "embeddings": embeddings,
        }
        return True

    def prepare_restore(self, metadata: dict[str, Any], data: dict[str, Any]) -> bool:
        """Prepare for restore operation (called by BackupRestoreService)."""
        # In FakeProvider, we don't need to do anything special
        # Just ensure IDs are strings
        if data.get("ids"):
            data["ids"] = [str(i) for i in data["ids"]]
        return True

    def get_embedding_model(self, collection_name: str) -> Optional[str]:
        """Get the embedding model for a collection (returns None for FakeProvider)."""
        return None

    def query_collection(
        self,
        collection_name: str,
        query_embeddings: Optional[list[list[float]]] = None,
        n_results: int = 10,
        where: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if collection_name not in self._collections:
            return None
        col = self._collections[collection_name]
        ids = col.get("ids", [])
        docs = col.get("documents", [])
        metadatas = col.get("metadatas", [])
        embeddings = col.get("embeddings", [])
        # Filter by metadata "where" if provided
        indices = [i for i, m in enumerate(metadatas) if self._matches_where(m, where)]

        # Simple distance: if no query_embeddings, return first n_results from filtered set
        if not query_embeddings:
            selected = indices[:n_results]
            return {
                "ids": [ids[i] for i in selected],
                "distances": [0.0 for _ in selected],
                "documents": [docs[i] for i in selected],
                "metadatas": [metadatas[i] for i in selected],
                "embeddings": [embeddings[i] for i in selected],
            }

        # If query embeddings provided, compute dot-product similarity for first query
        q = np.array(query_embeddings[0], dtype=float)
        emb_list = [
            embeddings[i] if embeddings[i] is not None else np.zeros_like(q) for i in indices
        ]
        if len(emb_list) == 0:
            return {"ids": [], "distances": [], "documents": [], "metadatas": [], "embeddings": []}

        emb_mat = np.array(emb_list, dtype=float)
        dots = emb_mat.dot(q)
        order_local = list(np.argsort(-dots))[:n_results]
        selected = [indices[i] for i in order_local]
        return {
            "ids": [ids[i] for i in selected],
            "distances": [float(-dots[j]) for j in order_local],
            "documents": [docs[i] for i in selected],
            "metadatas": [metadatas[i] for i in selected],
            "embeddings": [embeddings[i] for i in selected],
        }

    def get_all_items(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        if collection_name not in self._collections:
            return None
        col = self._collections[collection_name]
        ids = col.get("ids", [])
        docs = col.get("documents", [])
        metadatas = col.get("metadatas", [])
        embeddings = col.get("embeddings", [])

        # Apply where filtering if provided
        indices = [i for i, m in enumerate(metadatas) if self._matches_where(m, where)]
        start = offset or 0
        end = start + limit if limit is not None else len(indices)
        selected = indices[start:end]
        return {
            "ids": [ids[i] for i in selected],
            "documents": [docs[i] for i in selected],
            "metadatas": [metadatas[i] for i in selected],
            "embeddings": [embeddings[i] for i in selected],
        }

    def add_items(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: Optional[list[dict[str, Any]]] = None,
        ids: Optional[list[str]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> bool:
        self._ensure_collection(collection_name)
        col = self._collections[collection_name]
        if ids is None:
            ids = [str(uuid.uuid4()) for _ in documents]
        embeddings = embeddings or [None] * len(documents)
        metadatas = metadatas or [None] * len(documents)
        col["ids"].extend(ids)
        col["documents"].extend(documents)
        col["metadatas"].extend(metadatas)
        col["embeddings"].extend(embeddings)
        return True

    def update_items(
        self,
        collection_name: str,
        ids: list[str],
        documents: Optional[list[str]] = None,
        metadatas: Optional[list[dict[str, Any]]] = None,
        embeddings: Optional[list[list[float]]] = None,
    ) -> bool:
        self._ensure_collection(collection_name)
        if collection_name not in self._collections:
            return False
        col = self._collections[collection_name]
        for i, id_ in enumerate(ids):
            try:
                idx = col["ids"].index(id_)
            except ValueError:
                continue
            if documents and i < len(documents):
                col["documents"][idx] = documents[i]
            if metadatas and i < len(metadatas):
                col["metadatas"][idx] = metadatas[i]
            if embeddings and i < len(embeddings):
                col["embeddings"][idx] = embeddings[i]
        return True

    def delete_items(
        self,
        collection_name: str,
        ids: Optional[list[str]] = None,
        where: Optional[dict[str, Any]] = None,
    ) -> bool:
        if collection_name not in self._collections:
            return False
        col = self._collections[collection_name]
        if ids:
            new_ids, new_docs, new_metas, new_embs = [], [], [], []
            for i, id_ in enumerate(col["ids"]):
                if id_ not in ids:
                    new_ids.append(id_)
                    new_docs.append(col["documents"][i])
                    new_metas.append(col["metadatas"][i])
                    new_embs.append(col["embeddings"][i])
            col["ids"] = new_ids
            col["documents"] = new_docs
            col["metadatas"] = new_metas
            col["embeddings"] = new_embs
            return True

        if where:
            # delete items matching where filter
            new_ids, new_docs, new_metas, new_embs = [], [], [], []
            for i, meta in enumerate(col["metadatas"]):
                if not self._matches_where(meta, where):
                    new_ids.append(col["ids"][i])
                    new_docs.append(col["documents"][i])
                    new_metas.append(col["metadatas"][i])
                    new_embs.append(col["embeddings"][i])
            col["ids"] = new_ids
            col["documents"] = new_docs
            col["metadatas"] = new_metas
            col["embeddings"] = new_embs
            return True

        return False

    def delete_collection(self, name: str) -> bool:
        if name in self._collections:
            del self._collections[name]
            return True
        return False

    def get_connection_info(self) -> dict[str, Any]:
        return {"provider": "FakeProvider", "connected": self._connected}
