"""PgVector/PostgreSQL connection manager."""

from typing import Optional, List, Dict, Any
import json
import psycopg2
from psycopg2 import sql

## No need to import register_vector; pgvector extension is enabled at table creation
from vector_inspector.core.connections.base_connection import VectorDBConnection
from vector_inspector.core.logging import log_error


class PgVectorConnection(VectorDBConnection):
    """Manages connection to pgvector/PostgreSQL and provides query interface."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 5432,
        database: str = "subtitles",
        user: str = "postgres",
        password: str = "postgres",
    ):
        """
        Initialize PgVector/PostgreSQL connection.

        Args:
            host: Database host
            port: Database port
            database: Database name
            user: Username
            password: Password
        """
        self.host = host
        self.port = port
        self.database = database
        self.user = user
        self.password = password
        self._client: Optional[psycopg2.extensions.connection] = None

    def connect(self) -> bool:
        """
        Establish connection to PostgreSQL.

        Returns:
            True if connection successful, False otherwise
        """
        try:
            self._client = psycopg2.connect(
                host=self.host,
                port=self.port,
                database=self.database,
                user=self.user,
                password=self.password,
            )
            # Register pgvector adapter so Python lists can be passed as vector params
            try:
                from pgvector.psycopg2 import register_vector

                try:
                    register_vector(self._client)
                except Exception:
                    # Some versions accept connection or cursor; try both
                    try:
                        register_vector(self._client.cursor())
                    except Exception:
                        pass
            except Exception:
                pass
            return True
        except Exception as e:
            log_error("Connection failed: %s", e)
            self._client = None
            return False

    def disconnect(self):
        """Close connection to PostgreSQL."""
        if self._client:
            self._client.close()
        self._client = None

    @property
    def is_connected(self) -> bool:
        """Check if connected to PostgreSQL."""
        return self._client is not None

    def list_collections(self) -> List[str]:
        """
        Get list of all vector tables (collections).

        Returns:
            List of table names containing vector columns
        """
        if not self._client:
            return []
        try:
            with self._client.cursor() as cur:
                cur.execute("""
                    SELECT DISTINCT table_name FROM information_schema.columns
                    WHERE data_type = 'USER-DEFINED' 
                    AND udt_name = 'vector'
                    AND table_schema = 'public'
                """)
                tables = [row[0] for row in cur.fetchall()]
            return tables
        except Exception as e:
            log_error("Failed to list collections: %s", e)
            return []

    def list_databases(self) -> List[str]:
        """
        List available databases on the server (non-template databases).

        Returns:
            List of database names, or empty list on error
        """
        # Prefer using the existing client if available, otherwise open a short-lived connection
        conn = self._client
        tmp_conn = None
        try:
            if not conn:
                # Try connecting to the standard 'postgres' database as a safe default
                tmp_conn = psycopg2.connect(
                    host=self.host,
                    port=self.port,
                    database="postgres",
                    user=self.user,
                    password=self.password,
                )
                conn = tmp_conn

            with conn.cursor() as cur:
                cur.execute(
                    "SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY datname"
                )
                rows = cur.fetchall()
                return [r[0] for r in rows]
        except Exception as e:
            log_error("Failed to list databases: %s", e)
            return []
        finally:
            if tmp_conn:
                try:
                    tmp_conn.close()
                except Exception:
                    pass

    def get_collection_info(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get collection metadata and statistics.

        Args:
            name: Table name

        Returns:
            Dictionary with collection info
        """
        if not self._client:
            return None
        try:
            with self._client.cursor() as cur:
                # Use sql.Identifier to safely quote table name
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(name)))
                result = cur.fetchone()
                count = result[0] if result else 0

                # Get schema to identify metadata columns (exclude id, document, embedding)
                schema = self._get_table_schema(name)
                metadata_fields = [
                    col for col in schema.keys() if col not in ["id", "document", "embedding"]
                ]

                # Try to determine vector dimension and detect stored embedding model from a sample row
                vector_dimension = "Unknown"
                detected_model = None
                detected_model_type = None

                try:
                    cur.execute(
                        sql.SQL("SELECT embedding, metadata FROM {} LIMIT 1").format(
                            sql.Identifier(name)
                        )
                    )
                    sample = cur.fetchone()
                    if sample:
                        emb_val, meta_val = sample[0], sample[1]
                        # Determine vector dimension
                        try:
                            parsed = self._parse_vector(emb_val)
                            if parsed:
                                vector_dimension = len(parsed)
                        except Exception:
                            vector_dimension = "Unknown"

                        # Try to detect embedding model from metadata
                        meta_obj = None
                        if isinstance(meta_val, (str, bytes)):
                            try:
                                meta_obj = json.loads(meta_val)
                            except Exception:
                                meta_obj = None
                        elif isinstance(meta_val, dict):
                            meta_obj = meta_val

                        if meta_obj:
                            if "embedding_model" in meta_obj:
                                detected_model = meta_obj.get("embedding_model")
                                detected_model_type = meta_obj.get("embedding_model_type", "stored")
                            elif "_embedding_model" in meta_obj:
                                detected_model = meta_obj.get("_embedding_model")
                                detected_model_type = "stored"
                except Exception:
                    # Best-effort; non-fatal
                    pass

            result = {"name": name, "count": count, "metadata_fields": metadata_fields}
            if vector_dimension != "Unknown":
                result["vector_dimension"] = vector_dimension
            if detected_model:
                result["embedding_model"] = detected_model
                result["embedding_model_type"] = detected_model_type or "stored"

            return result
        except Exception as e:
            log_error("Failed to get collection info: %s", e)
            return None

    def create_collection(self, name: str, vector_size: int, distance: str = "cosine") -> bool:
        """
        Create a new table for storing vectors.

        Args:
            name: Table name
            vector_size: Dimension of vectors
            distance: Distance metric (cosine, euclidean, dotproduct, euclidean)

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        try:
            with self._client.cursor() as cur:
                # Ensure pgvector extension is enabled
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # Create table with TEXT id to support custom IDs from migrations/backups
                cur.execute(
                    sql.SQL(
                        "CREATE TABLE {} (id TEXT PRIMARY KEY, document TEXT, metadata JSONB, embedding vector({}))"
                    ).format(sql.Identifier(name), sql.Literal(vector_size))
                )

                # Map distance metric to pgvector index operator
                distance_lower = distance.lower()
                if distance_lower in ["cosine", "cos"]:
                    ops_class = "vector_cosine_ops"
                elif distance_lower in ["euclidean", "l2"]:
                    ops_class = "vector_l2_ops"
                elif distance_lower in ["dotproduct", "dot", "ip"]:
                    ops_class = "vector_ip_ops"
                else:
                    # Default to cosine
                    ops_class = "vector_cosine_ops"

                # Create index for vector similarity search
                index_name = f"{name}_embedding_idx"
                cur.execute(
                    sql.SQL("CREATE INDEX {} ON {} USING ivfflat (embedding {})").format(
                        sql.Identifier(index_name), sql.Identifier(name), sql.SQL(ops_class)
                    )
                )
                self._client.commit()
            return True
        except Exception as e:
            log_error("Failed to create collection: %s", e)
            if self._client:
                self._client.rollback()
            return False

    def add_items(
        self,
        collection_name: str,
        documents: List[str],
        metadatas: Optional[List[Dict[str, Any]]] = None,
        ids: Optional[List[str]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Add items to a collection.

        Args:
            collection_name: Table name
            documents: Document texts
            metadatas: Metadata for each document (optional)
            ids: IDs for each document (required for proper migration support)
            embeddings: Pre-computed embeddings

        Returns:
            True if successful, False otherwise
        """
        if not self._client or not embeddings:
            return False
        try:
            import uuid

            # Get table schema to determine column structure
            schema = self._get_table_schema(collection_name)
            has_metadata_col = "metadata" in schema

            with self._client.cursor() as cur:
                for i, emb in enumerate(embeddings):
                    # Use provided ID or generate a UUID
                    item_id = ids[i] if ids and i < len(ids) else str(uuid.uuid4())
                    doc = documents[i] if i < len(documents) else None
                    metadata = metadatas[i] if metadatas and i < len(metadatas) else {}
                    # Build insert statement based on schema
                    if has_metadata_col:
                        # Use JSONB metadata column
                        metadata_json = json.dumps(metadata) if metadata else None
                        cur.execute(
                            sql.SQL(
                                "INSERT INTO {} (id, document, metadata, embedding) VALUES (%s, %s, %s, %s)"
                            ).format(sql.Identifier(collection_name)),
                            (item_id, doc, metadata_json, emb),
                        )
                    else:
                        # Map metadata to specific columns
                        columns = ["id", "embedding"]
                        values = [item_id, emb]

                        if "document" in schema and doc is not None:
                            columns.append("document")
                            values.append(doc)

                        # Add metadata fields that exist as columns
                        if metadata:
                            for key, value in metadata.items():
                                if key in schema:
                                    columns.append(key)
                                    values.append(value)

                        placeholders = ", ".join(["%s"] * len(values))
                        cur.execute(
                            sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                                sql.Identifier(collection_name),
                                sql.SQL(", ").join(sql.Identifier(c) for c in columns),
                                sql.SQL(placeholders),
                            ),
                            values,
                        )
                self._client.commit()
            return True
        except Exception as e:
            log_error("Failed to add items: %s", e)
            if self._client:
                self._client.rollback()
            return False

    def get_items(self, name: str, ids: List[str]) -> Dict[str, Any]:
        """
        Retrieve items by IDs.

        Args:
            name: Table name
            ids: List of IDs

        Returns:
            Dict with 'documents', 'metadatas', 'embeddings'
        """
        if not self._client:
            return {}
        try:
            schema = self._get_table_schema(name)
            has_metadata_col = "metadata" in schema

            with self._client.cursor() as cur:
                # Select all columns
                cur.execute(
                    sql.SQL("SELECT * FROM {} WHERE id = ANY(%s)").format(sql.Identifier(name)),
                    (ids,),
                )
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]

            # Build results
            result_ids = []
            result_docs = []
            result_metas = []
            result_embeds = []

            for row in rows:
                row_dict = dict(zip(colnames, row))
                result_ids.append(str(row_dict.get("id", "")))
                result_docs.append(row_dict.get("document", ""))

                # Handle metadata
                if has_metadata_col:
                    meta = row_dict.get("metadata")
                    if isinstance(meta, (str, bytes)):
                        try:
                            parsed_meta = json.loads(meta)
                        except Exception:
                            parsed_meta = {}
                    elif isinstance(meta, dict):
                        parsed_meta = meta
                    else:
                        parsed_meta = {}
                    result_metas.append(parsed_meta)
                else:
                    # Reconstruct metadata from columns
                    metadata = {
                        k: v
                        for k, v in row_dict.items()
                        if k not in ["id", "document", "embedding"]
                    }
                    result_metas.append(metadata)

                # Handle embedding
                result_embeds.append(self._parse_vector(row_dict.get("embedding", "")))

            return {
                "ids": result_ids,
                "documents": result_docs,
                "metadatas": result_metas,
                "embeddings": result_embeds,
            }
        except Exception as e:
            log_error("Failed to get items: %s", e)
            return {}

    def delete_collection(self, name: str) -> bool:
        """
        Delete a table (collection).

        Args:
            name: Table name

        Returns:
            True if successful, False otherwise
        """
        if not self._client:
            return False
        try:
            with self._client.cursor() as cur:
                cur.execute(sql.SQL("DROP TABLE IF EXISTS {} CASCADE").format(sql.Identifier(name)))
                self._client.commit()
            return True
        except Exception as e:
            log_error("Failed to delete collection: %s", e)
            if self._client:
                self._client.rollback()
            return False

    def count_collection(self, name: str) -> int:
        """
        Return the number of items in the collection.

        Args:
            name: Table name

        Returns:
            Number of items
        """
        if not self._client:
            return 0
        try:
            with self._client.cursor() as cur:
                cur.execute(sql.SQL("SELECT COUNT(*) FROM {}").format(sql.Identifier(name)))
                result = cur.fetchone()
                count = result[0] if result else 0
            return count
        except Exception as e:
            log_error("Failed to count collection: %s", e)
            return 0

    def query_collection(
        self,
        collection_name: str,
        query_texts: Optional[List[str]] = None,
        query_embeddings: Optional[List[List[float]]] = None,
        n_results: int = 10,
        where: Optional[Dict[str, Any]] = None,
        where_document: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Query a collection for similar vectors.

        Args:
            collection_name: Table name
            query_embeddings: Embedding vectors to search
            n_results: Number of results to return
            where: Metadata filter (dict of column:value pairs)
            where_document: Document filter (not implemented)

        Returns:
            Query results dictionary
        """
        if not self._client or not query_embeddings:
            return None
        try:
            schema = self._get_table_schema(collection_name)
            has_metadata_col = "metadata" in schema

            with self._client.cursor() as cur:
                # Only supports single query embedding for now
                emb = query_embeddings[0]
                # Build query with optional WHERE clause. Pass embedding list directly
                query_parts = [
                    sql.SQL("SELECT *, embedding <=> %s AS distance FROM {}").format(
                        sql.Identifier(collection_name)
                    )
                ]
                params = [emb]

                # Add WHERE clause for filtering
                if where:
                    conditions = []
                    for key, value in where.items():
                        if has_metadata_col and key != "metadata":
                            # Filter on JSONB metadata column
                            conditions.append(sql.SQL("metadata->>%s = %s"))
                            params.extend([key, str(value)])
                        elif key in schema:
                            # Filter on actual column
                            conditions.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                            params.append(value)

                    if conditions:
                        query_parts.append(sql.SQL(" WHERE "))
                        query_parts.append(sql.SQL(" AND ").join(conditions))

                query_parts.append(sql.SQL(" ORDER BY distance ASC LIMIT %s"))
                params.append(n_results)

                query = sql.SQL("").join(query_parts)
                cur.execute(query, params)
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]

            # Build results
            result_ids = []
            result_docs = []
            result_metas = []
            result_embeds = []
            result_dists = []

            for row in rows:
                row_dict = dict(zip(colnames, row))
                result_ids.append([str(row_dict.get("id", ""))])
                result_docs.append([row_dict.get("document", "")])

                # Handle metadata
                if has_metadata_col:
                    meta = row_dict.get("metadata")
                    if isinstance(meta, (str, bytes)):
                        try:
                            parsed_meta = json.loads(meta)
                        except Exception:
                            parsed_meta = {}
                    elif isinstance(meta, dict):
                        parsed_meta = meta
                    else:
                        parsed_meta = {}
                    result_metas.append([parsed_meta])
                else:
                    # Reconstruct metadata from columns
                    metadata = {
                        k: v
                        for k, v in row_dict.items()
                        if k not in ["id", "document", "embedding", "distance"]
                    }
                    result_metas.append([metadata])

                # Handle embedding and distance
                result_embeds.append([self._parse_vector(row_dict.get("embedding", ""))])
                result_dists.append([float(row_dict.get("distance", 0))])

            return {
                "ids": result_ids,
                "documents": result_docs,
                "metadatas": result_metas,
                "embeddings": result_embeds,
                "distances": result_dists,
            }
        except Exception as e:
            log_error("Query failed: %s", e)
            return None

    def get_all_items(
        self,
        collection_name: str,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Get all items from a collection.

        Args:
            collection_name: Table name
            limit: Max items
            offset: Offset
            where: Metadata filter (dict of column:value pairs)

        Returns:
            Dict with items
        """
        if not self._client:
            return None
        try:
            schema = self._get_table_schema(collection_name)
            has_metadata_col = "metadata" in schema

            with self._client.cursor() as cur:
                query_parts = [sql.SQL("SELECT * FROM {}").format(sql.Identifier(collection_name))]
                params = []

                # Add WHERE clause for filtering
                if where:
                    conditions = []
                    for key, value in where.items():
                        if has_metadata_col and key != "metadata":
                            # Filter on JSONB metadata column
                            conditions.append(sql.SQL("metadata->>%s = %s"))
                            params.extend([key, str(value)])
                        elif key in schema:
                            # Filter on actual column
                            conditions.append(sql.SQL("{} = %s").format(sql.Identifier(key)))
                            params.append(value)

                    if conditions:
                        query_parts.append(sql.SQL(" WHERE "))
                        query_parts.append(sql.SQL(" AND ").join(conditions))

                if limit:
                    query_parts.append(sql.SQL(" LIMIT %s"))
                    params.append(limit)
                if offset:
                    query_parts.append(sql.SQL(" OFFSET %s"))
                    params.append(offset)

                query = sql.SQL("").join(query_parts)
                cur.execute(query, params if params else None)
                rows = cur.fetchall()
                colnames = [desc[0] for desc in cur.description]

            # Build results
            result_ids = []
            result_docs = []
            result_metas = []
            result_embeds = []

            for row in rows:
                row_dict = dict(zip(colnames, row))
                result_ids.append(str(row_dict.get("id", "")))
                result_docs.append(row_dict.get("document", ""))

                # Handle metadata
                if has_metadata_col:
                    meta = row_dict.get("metadata")
                    if isinstance(meta, (str, bytes)):
                        try:
                            parsed_meta = json.loads(meta)
                        except Exception:
                            parsed_meta = {}
                    elif isinstance(meta, dict):
                        parsed_meta = meta
                    else:
                        parsed_meta = {}
                    result_metas.append(parsed_meta)
                else:
                    # Reconstruct metadata from columns
                    metadata = {
                        k: v
                        for k, v in row_dict.items()
                        if k not in ["id", "document", "embedding"]
                    }
                    result_metas.append(metadata)

                # Handle embedding
                result_embeds.append(self._parse_vector(row_dict.get("embedding", "")))

            return {
                "ids": result_ids,
                "documents": result_docs,
                "metadatas": result_metas,
                "embeddings": result_embeds,
            }
        except Exception as e:
            log_error("Failed to get items: %s", e)
            return None

    def update_items(
        self,
        collection_name: str,
        ids: List[str],
        documents: Optional[List[str]] = None,
        metadatas: Optional[List[Dict[str, Any]]] = None,
        embeddings: Optional[List[List[float]]] = None,
    ) -> bool:
        """
        Update items in a collection.

        Args:
            collection_name: Table name
            ids: IDs to update
            documents: New docs
            metadatas: New metadata
            embeddings: New embeddings

        Returns:
            True if successful, False otherwise
        """
        if not self._client or not ids:
            return False
        try:
            # If embeddings are not provided but documents were, compute embeddings
            embeddings_local = embeddings
            if (not embeddings) and documents:
                try:
                    # Resolve model for this collection: prefer settings -> collection metadata -> dimension-based
                    from vector_inspector.services.settings_service import SettingsService
                    from vector_inspector.core.embedding_utils import (
                        load_embedding_model,
                        get_embedding_model_for_dimension,
                        DEFAULT_MODEL,
                    )

                    model_name = None
                    model_type = None

                    # 1) settings
                    settings = SettingsService()
                    model_info = settings.get_embedding_model(self.database, collection_name)
                    if model_info:
                        model_name = model_info.get("model")
                        model_type = model_info.get("type", "sentence-transformer")

                    # 2) collection metadata
                    if not model_name:
                        coll_info = self.get_collection_info(collection_name)
                        if coll_info and coll_info.get("embedding_model"):
                            model_name = coll_info.get("embedding_model")
                            model_type = coll_info.get("embedding_model_type", "stored")

                    # 3) dimension-based fallback
                    loaded_model = None
                    if not model_name:
                        # Try to get vector dimension
                        dim = None
                        coll_info = self.get_collection_info(collection_name)
                        if coll_info and coll_info.get("vector_dimension"):
                            try:
                                dim = int(coll_info.get("vector_dimension"))
                            except Exception:
                                dim = None
                        if dim:
                            loaded_model, model_name, model_type = (
                                get_embedding_model_for_dimension(dim)
                            )
                        else:
                            # Use default model
                            model_name, model_type = DEFAULT_MODEL

                    # Load model if not already loaded
                    if not loaded_model:
                        loaded_model = load_embedding_model(model_name, model_type)

                    # Compute embeddings only for documents that are present
                    compute_idxs = [i for i, d in enumerate(documents) if d]
                    if compute_idxs:
                        docs_to_compute = [documents[i] for i in compute_idxs]
                        # Use SentenceTransformer batch encode when possible
                        if model_type != "clip":
                            computed = loaded_model.encode(
                                docs_to_compute, show_progress_bar=False
                            ).tolist()
                        else:
                            # CLIP type - encode per document using helper
                            from vector_inspector.core.embedding_utils import encode_text

                            computed = [
                                encode_text(d, loaded_model, model_type) for d in docs_to_compute
                            ]
                        embeddings_local = [None] * len(ids)
                        for idx, emb in zip(compute_idxs, computed):
                            embeddings_local[idx] = emb
                except Exception as e:
                    log_error("Failed to compute embeddings on update: %s", e)
                    embeddings_local = [None] * len(ids)

            with self._client.cursor() as cur:
                for i, item_id in enumerate(ids):
                    updates = []
                    params = []

                    if documents and i < len(documents):
                        updates.append(sql.SQL("document = %s"))
                        params.append(documents[i])

                    if metadatas and i < len(metadatas):
                        updates.append(sql.SQL("metadata = %s"))
                        params.append(json.dumps(metadatas[i]))

                    # Use provided embeddings if present, otherwise use locally computed embedding
                    emb_to_use = None
                    if embeddings and i < len(embeddings):
                        emb_to_use = embeddings[i]
                    elif embeddings_local and i < len(embeddings_local):
                        emb_to_use = embeddings_local[i]

                    if emb_to_use is not None:
                        updates.append(sql.SQL("embedding = %s"))
                        params.append(emb_to_use)

                    if updates:
                        params.append(item_id)
                        query = sql.SQL("UPDATE {} SET {} WHERE id = %s").format(
                            sql.Identifier(collection_name), sql.SQL(", ").join(updates)
                        )
                        cur.execute(query, params)

                self._client.commit()
            return True
        except Exception as e:
            log_error("Failed to update items: %s", e)
            if self._client:
                self._client.rollback()
            return False

    def delete_items(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        where: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """
        Delete items from a collection.

        Args:
            collection_name: Table name
            ids: IDs to delete
            where: Metadata filter (not implemented)

        Returns:
            True if successful, False otherwise
        """
        if not self._client or not ids:
            return False
        try:
            with self._client.cursor() as cur:
                cur.execute(
                    sql.SQL("DELETE FROM {} WHERE id = ANY(%s)").format(
                        sql.Identifier(collection_name)
                    ),
                    (ids,),
                )
                self._client.commit()
            return True
        except Exception as e:
            log_error("Failed to delete items: %s", e)
            if self._client:
                self._client.rollback()
            return False

    def get_connection_info(self) -> Dict[str, Any]:
        """
        Get information about the current connection.

        Returns:
            Dictionary with connection details
        """
        return {
            "provider": "PgVector/PostgreSQL",
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "connected": self.is_connected,
        }

    def _get_table_schema(self, table_name: str) -> Dict[str, str]:
        """
        Get the schema (column names and types) for a table.

        Args:
            table_name: Name of the table

        Returns:
            Dict mapping column names to their SQL types
        """
        if not self._client:
            return {}
        try:
            with self._client.cursor() as cur:
                cur.execute(
                    """SELECT column_name, data_type, udt_name 
                       FROM information_schema.columns 
                       WHERE table_name = %s AND table_schema = 'public'
                       ORDER BY ordinal_position""",
                    (table_name,),
                )
                schema = {}
                for row in cur.fetchall():
                    col_name, data_type, udt_name = row
                    # Use udt_name for custom types like vector
                    schema[col_name] = udt_name if data_type == "USER-DEFINED" else data_type
                return schema
        except Exception as e:
            log_error("Failed to get table schema: %s", e)
            return {}

    def _parse_vector(self, vector_str: Any) -> List[float]:
        """
        Parse pgvector string format to Python list.

        Args:
            vector_str: Vector in string format from database

        Returns:
            List of floats
        """
        if isinstance(vector_str, list):
            return vector_str
        if isinstance(vector_str, str):
            # Remove brackets and split by comma
            vector_str = vector_str.strip("[]")
            return [float(x) for x in vector_str.split(",")]
        return []
