"""LanceDB connection implementation for Vector Inspector."""

import os
from typing import Any

import lancedb
from vector_inspector.core.logging import log_error

from .base_connection import VectorDBConnection


class LanceDBConnection(VectorDBConnection):
    """LanceDB vector database connection."""

    def __init__(self, uri: str = "./lancedb", **kwargs):
        """
        Initialize LanceDB connection parameters.
        Args:
                uri: Path or URI to LanceDB database
                **kwargs: Additional LanceDB options
        """
        self._uri = uri
        self._client = None
        self._db = None
        self._connected = False

    def connect(self) -> bool:
        try:
            # Ensure path is absolute for consistent behavior across working dirs
            if isinstance(self._uri, str) and "://" not in self._uri:
                self._uri = os.path.abspath(os.path.expanduser(self._uri))
            self._db = lancedb.connect(self._uri)
            print(f"LanceDB connect: uri={self._uri}")
            self._client = self._db
            self._connected = True
            return True
        except Exception as e:
            log_error("LanceDB connection failed: %s", e)
            self._connected = False
            return False

    def disconnect(self):
        self._client = None
        self._db = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def list_collections(self) -> list[str]:
        if not self.is_connected:
            return []
        tables_info = self._db.list_tables()
        # LanceDB always returns a dict with 'tables' as a list of collection names
        if isinstance(tables_info, dict):
            return [name for name in tables_info.get("tables", []) if isinstance(name, str)]
        if hasattr(tables_info, "tables"):
            return [name for name in getattr(tables_info, "tables", []) if isinstance(name, str)]
        return []

    def get_collection_info(self, name: str) -> dict[str, Any] | None:
        if not self.is_connected:
            return None
        try:
            tbl = self._db.open_table(name)
            # Row count (prefer num_rows, fallback to pandas length)
            count = getattr(tbl, "num_rows", None)

            # Pull dataframe sample to infer metadata fields and vector dimension
            try:
                df = tbl.to_pandas()
            except Exception:
                df = None

            metadata_fields: list[str] = []
            vector_dimension: int | str = "Unknown"

            if df is not None and not df.empty:
                # Determine count if not available
                if count is None:
                    try:
                        count = len(df)
                    except Exception:
                        count = 0

                # Infer metadata fields from the first row
                first_meta = df.iloc[0].get("metadata") if "metadata" in df.columns else None
                if isinstance(first_meta, str):
                    import ast

                    try:
                        parsed = ast.literal_eval(first_meta)
                        if isinstance(parsed, dict):
                            metadata_fields = list(parsed.keys())
                    except Exception:
                        # treat as raw string field
                        metadata_fields = []
                elif isinstance(first_meta, dict):
                    metadata_fields = list(first_meta.keys())

                # Infer vector dimension from the first vector entry
                if "vector" in df.columns:
                    first_vec = df.iloc[0].get("vector")
                    if first_vec is not None:
                        try:
                            vector_dimension = len(first_vec)
                        except Exception:
                            vector_dimension = "Unknown"

            else:
                # No dataframe available, try to get count from attribute
                if count is None:
                    count = 0

            distance_metric = "Unknown"

            return {
                "name": name,
                "count": int(count) if count is not None else 0,
                "metadata_fields": metadata_fields,
                "vector_dimension": vector_dimension,
                "distance_metric": distance_metric,
            }
        except Exception as e:
            log_error("LanceDB get_collection_info failed: %s", e)
            return None

    def create_collection(self, name: str, vector_size: int, distance: str = "Cosine") -> bool:
        if not self.is_connected:
            return False
        try:
            import pyarrow as pa

            # Use fixed_size_list for vectors to capture the known vector dimension
            schema = pa.schema(
                [
                    pa.field("vector", pa.fixed_size_list(pa.float32(), vector_size)),
                    pa.field("id", pa.string()),
                    pa.field("metadata", pa.string()),
                ]
            )
            print(f"LanceDB create_collection: Creating table '{name}' with schema {schema}")
            self._db.create_table(name, schema=schema)
            print(f"LanceDB create_collection: Table '{name}' created successfully")
            return True
        except Exception as e:
            print(f"LanceDB create_collection failed: {e}")
            return False

    def add_items(
        self,
        collection_name: str,
        documents: list[str],
        metadatas: list[dict[str, Any]] | None = None,
        ids: list[str] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> bool:
        if not self.is_connected:
            return False
        try:
            tbl = self._db.open_table(collection_name)
            import pyarrow as pa

            # Prepare data
            vectors = embeddings if embeddings else [[0.0] * len(documents)] * len(documents)
            meta = metadatas if metadatas else [{}] * len(documents)
            id_list = ids if ids else [str(i) for i in range(len(documents))]
            arr = pa.table({"vector": vectors, "id": id_list, "metadata": [str(m) for m in meta]})
            tbl.add(arr)
            return True
        except Exception as e:
            log_error("LanceDB add_items failed: %s", e)
            return False

    def get_items(self, name: str, ids: list[str]) -> dict[str, Any]:
        if not self.is_connected:
            return {}
        try:
            tbl = self._db.open_table(name)
            df = tbl.to_pandas()
            filtered = df[df["id"].isin(ids)]
            # Convert metadata strings to dicts if possible
            import ast

            metadatas = []
            for m in filtered["metadata"].tolist():
                if isinstance(m, str):
                    try:
                        metadatas.append(ast.literal_eval(m))
                    except Exception:
                        metadatas.append({"raw": m})
                else:
                    metadatas.append(m)
            return {
                "documents": filtered["metadata"].tolist(),
                "metadatas": metadatas,
            }
        except Exception as e:
            log_error("LanceDB get_items failed: %s", e)
            return {}

    def _parse_metadata_list(self, raw_list: list) -> list[dict[str, Any]]:
        """Parse a list of metadata values (strings or dicts) into list of dicts."""
        import ast

        parsed: list[dict[str, Any]] = []
        for m in raw_list:
            if isinstance(m, str):
                try:
                    val = ast.literal_eval(m)
                    if isinstance(val, dict):
                        parsed.append(val)
                    else:
                        parsed.append({"raw": m})
                except Exception:
                    parsed.append({"raw": m})
            elif isinstance(m, dict):
                parsed.append(m)
            else:
                parsed.append({"raw": str(m)})
        return parsed

    def delete_collection(self, name: str) -> bool:
        if not self.is_connected:
            return False
        try:
            self._db.drop_table(name)
            return True
        except Exception as e:
            log_error("LanceDB delete_collection failed: %s", e)
            return False

    def count_collection(self, name: str) -> int:
        if not self.is_connected:
            return 0
        try:
            tbl = self._db.open_table(name)
            # LanceTable exposes num_rows; fall back to pandas length if needed
            count = getattr(tbl, "num_rows", None)
            if count is not None:
                try:
                    return int(count)
                except Exception:
                    pass
            try:
                df = tbl.to_pandas()
                return len(df)
            except Exception:
                return 0
        except Exception as e:
            log_error("LanceDB count_collection failed: %s", e)
            return 0

    def query_collection(
        self,
        collection_name: str,
        query_texts: list[str] | None = None,
        query_embeddings: list[list[float]] | None = None,
        n_results: int = 10,
        where: dict[str, Any] | None = None,
        where_document: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_connected:
            return None
        try:
            tbl = self._db.open_table(collection_name)
            # LanceDB supports search by embedding. Ensure embedding dim matches collection dim.
            # Resolve collection vector dimension if possible
            try:
                info = self.get_collection_info(collection_name)
                coll_dim = info.get("vector_dimension") if info else None
                if isinstance(coll_dim, str) and coll_dim.isdigit():
                    coll_dim = int(coll_dim)
            except Exception:
                coll_dim = None

            # If query_texts provided but no embeddings, compute embeddings for the collection
            if (not query_embeddings) and query_texts:
                try:
                    query_embeddings = self.compute_embeddings_for_documents(
                        collection_name, query_texts
                    )
                except Exception as e:
                    log_error("Failed to compute embeddings for query_texts: %s", e)
                    return None

            if query_embeddings:
                emb = query_embeddings[0]
                if coll_dim and len(emb) != int(coll_dim):
                    # Try to recompute embeddings from query_texts if available
                    if query_texts:
                        try:
                            query_embeddings = self.compute_embeddings_for_documents(
                                collection_name, query_texts
                            )
                            emb = query_embeddings[0]
                        except Exception as e:
                            log_error("Embedding dim mismatch and recompute failed: %s", e)
                            return None
                    else:
                        log_error(
                            "Embedding dim mismatch: query dim(%d) != collection dim(%s)",
                            len(emb),
                            str(coll_dim),
                        )
                        return None

                results = tbl.search(emb).limit(n_results).to_pandas()
                raw_meta = results["metadata"].tolist() if "metadata" in results else []
                metadatas = self._parse_metadata_list(raw_meta)
                # Documents: try to use a 'document' key if present in metadata, else raw metadata
                documents = [
                    m.get("document") if isinstance(m, dict) and "document" in m else str(raw)
                    for raw, m in zip(raw_meta, metadatas)
                ]
                return {
                    "ids": results["id"].tolist(),
                    "distances": results["score"].tolist() if "score" in results else [],
                    "documents": documents,
                    "metadatas": metadatas,
                    "embeddings": results["vector"].tolist() if "vector" in results else [],
                }
            return None
        except Exception as e:
            log_error("LanceDB query_collection failed: %s", e)
            return None

    def get_all_items(
        self,
        collection_name: str,
        limit: int | None = None,
        offset: int | None = None,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        if not self.is_connected:
            return None
        try:
            tbl = self._db.open_table(collection_name)
            df = tbl.to_pandas()
            if offset:
                df = df[offset:]
            if limit:
                df = df[:limit]
            raw_meta = df["metadata"].tolist() if "metadata" in df.columns else []
            metadatas = self._parse_metadata_list(raw_meta)
            # Documents: prefer 'document' key inside metadata if present
            documents = [
                m.get("document") if isinstance(m, dict) and "document" in m else str(raw)
                for raw, m in zip(raw_meta, metadatas)
            ]
            return {
                "ids": df["id"].tolist(),
                "documents": documents,
                "metadatas": metadatas,
                "embeddings": df["vector"].tolist() if "vector" in df.columns else [],
            }
        except Exception as e:
            log_error("LanceDB get_all_items failed: %s", e)
            return None

    def update_items(
        self,
        collection_name: str,
        ids: list[str],
        documents: list[str] | None = None,
        metadatas: list[dict[str, Any]] | None = None,
        embeddings: list[list[float]] | None = None,
    ) -> bool:
        # LanceDB does not support update, so delete and re-add
        if not self.is_connected:
            return False
        try:
            self.delete_items(collection_name, ids=ids)
            return self.add_items(collection_name, documents or [], metadatas, ids, embeddings)
        except Exception as e:
            log_error("LanceDB update_items failed: %s", e)
            return False

    def delete_items(
        self,
        collection_name: str,
        ids: list[str] | None = None,
        where: dict[str, Any] | None = None,
    ) -> bool:
        if not self.is_connected:
            return False
        try:
            tbl = self._db.open_table(collection_name)
            df = tbl.to_pandas()
            if ids:
                df = df[~df["id"].isin(ids)]
            # Re-create table with remaining items
            import pyarrow as pa

            arr = pa.table(
                {
                    "vector": df["vector"].tolist(),
                    "id": df["id"].tolist(),
                    "metadata": df["metadata"].tolist(),
                }
            )
            self._db.drop_table(collection_name)
            self._db.create_table(collection_name, arr.schema)
            self._db.open_table(collection_name).add(arr)
            return True
        except Exception as e:
            log_error("LanceDB delete_items failed: %s", e)
            return False
