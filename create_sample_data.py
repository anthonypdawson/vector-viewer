"""Sample script to populate ChromaDB with test data."""

from chromadb.utils import embedding_functions
import argparse
import sys

# Embedding model used for all sample data
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


def create_sample_data_chroma(
    collection: str = "sample_documents",
    path: str = "./chroma_data",
    embedding_model: str = EMBEDDING_MODEL,
):
    """Create sample data for ChromaDB with configurable options."""
    print("Creating sample ChromaDB data...")
    import chromadb

    client = chromadb.PersistentClient(path=path)
    collection_obj = client.get_or_create_collection(
        name=collection,
        metadata={
            "description": "Sample documents for testing",
            "embedding_model": embedding_model,
        },
    )
    documents, metadatas, ids = get_sample_docs()
    # Add model metadata to each document
    for metadata in metadatas:
        metadata["_embedding_model"] = embedding_model
    collection_obj.add(documents=documents, metadatas=metadatas, ids=ids)  # type: ignore
    print(f"Added {len(documents)} documents to collection '{collection_obj.name}'")
    print(f"Collection now contains {collection_obj.count()} items")
    print("\nYou can now:")
    print("1. Run the Vector Inspector application")
    print(f"2. Connect to Persistent storage with path: {path}")
    print(f"3. Select the '{collection}' collection")
    print("4. Browse, search, and visualize the data!")


def create_sample_data_qdrant(
    host="localhost",
    port=6333,
    collection_name="sample_documents",
    vector_size=384,
    path: str | None = None,
):
    """Create sample data for Qdrant (remote or local path)."""
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct
    from sentence_transformers import SentenceTransformer

    if path:
        print(f"Creating sample Qdrant data in local path '{path}'...")
        client = QdrantClient(path=path, check_compatibility=False)
    else:
        print(f"Creating sample Qdrant data on {host}:{port}...")
        client = QdrantClient(host=host, port=port, prefer_grpc=False, check_compatibility=False)
    # Delete collection if it exists (to avoid config mismatch)
    try:
        client.delete_collection(collection_name=collection_name)
        print(f"Deleted existing collection '{collection_name}' (if it existed)")
    except Exception as e:
        print(f"Could not delete collection (may not exist): {e}")
    # Try to create collection (ignore if exists)
    try:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        print(f"Created collection '{collection_name}' with vector size {vector_size}")
    except Exception as e:
        print(f"Collection may already exist: {e}")

    documents, metadatas, ids = get_sample_docs()
    # Generate embeddings
    print("Generating embeddings with sentence-transformers (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(documents, show_progress_bar=True).tolist()

    # Build points list
    points = []
    for i in range(len(documents)):
        point = PointStruct(
            id=i,  # Use integer IDs for Qdrant compatibility
            vector=embeddings[i],
            payload={
                "doc_id": ids[i],  # Store original string ID in payload
                "document": documents[i],
                "_embedding_model": EMBEDDING_MODEL,  # Store model used
                **metadatas[i],
            },
        )
        points.append(point)

    # Add to Qdrant
    print(f"Upserting {len(points)} points to Qdrant...")
    client.upsert(collection_name=collection_name, points=points)
    print(f"Added {len(documents)} documents to collection '{collection_name}'")
    print("\nYou can now:")
    print(f"1. Run the Vector Inspector application")
    if path:
        print(f"2. Connect to Qdrant (Local Path) at: {path}")
    else:
        print(f"2. Connect to Qdrant at {host}:{port}")
    print(f"3. Select the '{collection_name}' collection")
    print("4. Browse, search, and visualize the data!")


def create_sample_data_pgvector(
    host: str = "localhost",
    port: int = 5432,
    database: str = "postgres",
    user: str = "postgres",
    password: str | None = None,
    table_name: str = "sample_documents",
    vector_size: int = 384,
    flat_metadata: bool = False,
):
    """Create sample data in a Postgres database using the pgvector extension.

    This will create the `pgvector` extension if missing, create a table with a
    `vector` column, and upsert sample rows with embeddings.
    """
    print(f"Creating sample pgvector data in {host}:{port}/{database} -> table {table_name}...")

    try:
        import psycopg2
        import psycopg2.extras as extras
    except Exception as e:
        print("Error: psycopg2 is required to populate pgvector data:", e)
        return

    # Connect
    conn = psycopg2.connect(host=host, port=port, dbname=database, user=user, password=password)
    cur = conn.cursor()

    # Try to register pgvector adapter if available
    try:
        from pgvector.psycopg2 import register_vector

        register_vector(cur)
    except Exception:
        # If pgvector adapter not available, continue — psycopg2 may still accept lists
        pass

    # Ensure extension (table creation happens after we inspect metadata keys)
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    documents, metadatas, ids = get_sample_docs()

    # Ensure embedding model is recorded in metadata for all items
    for m in metadatas:
        if isinstance(m, dict):
            m["_embedding_model"] = EMBEDDING_MODEL

    # Determine metadata keys (for flat metadata mode)
    metadata_keys = []
    if flat_metadata:
        keys = set()
        for m in metadatas:
            if isinstance(m, dict):
                keys.update(m.keys())
        metadata_keys = sorted(keys)

    # Create table according to flat_metadata choice
    try:
        # If table exists, drop it and recreate to ensure a clean sample dataset
        try:
            cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
            print(f"Dropped existing table if present: {table_name}")
        except Exception:
            # best-effort drop; continue if it fails
            pass

        if flat_metadata and metadata_keys:
            # Create table with explicit metadata columns
            cols = ",\n            ".join(f"{k} TEXT" for k in metadata_keys)
            create_sql = f"""
            CREATE TABLE {table_name} (
                id TEXT PRIMARY KEY,
                embedding vector({vector_size}),
                document TEXT,
                {cols}
            )
            """
            cur.execute(create_sql)
            # Create simple indexes for flattened metadata columns to help filtering
            try:
                for k in metadata_keys:
                    idx_name = f"{table_name}_{k}_idx"
                    cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table_name} ({k})")
            except Exception as ie:
                print("Warning: failed to create index for metadata column:", ie)
        else:
            # Default: use JSONB metadata column
            cur.execute(
                f"""
                CREATE TABLE {table_name} (
                    id TEXT PRIMARY KEY,
                    embedding vector({vector_size}),
                    document TEXT,
                    metadata JSONB
                )
                """
            )
    except Exception as e:
        print("Warning: failed to create table as requested:", e)

    print("Generating embeddings with sentence-transformers (all-MiniLM-L6-v2)...")
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(documents, show_progress_bar=True).tolist()

    # Build rows and insert depending on flat_metadata
    if flat_metadata and metadata_keys:
        rows = []
        for i in range(len(documents)):
            row_vals = [ids[i], embeddings[i], documents[i]]
            md = metadatas[i] if i < len(metadatas) and isinstance(metadatas[i], dict) else {}
            for k in metadata_keys:
                row_vals.append(md.get(k))
            rows.append(tuple(row_vals))

        columns = ["id", "embedding", "document"] + metadata_keys
        cols_sql = ", ".join(columns)
        placeholders = "(" + ", ".join(["%s"] * len(columns)) + ")"
        update_sql = ", ".join([f"{col} = EXCLUDED.{col}" for col in columns if col != "id"])
        insert_sql = f"INSERT INTO {table_name} ({cols_sql}) VALUES %s ON CONFLICT (id) DO UPDATE SET {update_sql}"

        try:
            extras.execute_values(cur, insert_sql, rows, template=placeholders)
            conn.commit()
            print(f"Added/updated {len(rows)} documents to table '{table_name}'")
        except Exception as e:
            conn.rollback()
            print("Failed to insert rows:", e)
    else:
        # Default behavior: store metadata JSONB
        rows = []
        for i in range(len(documents)):
            rows.append((ids[i], embeddings[i], documents[i], extras.Json(metadatas[i])))

        # Upsert in a single statement using execute_values
        insert_sql = (
            f"INSERT INTO {table_name} (id, embedding, document, metadata) VALUES %s "
            f"ON CONFLICT (id) DO UPDATE SET embedding = EXCLUDED.embedding, document = EXCLUDED.document, metadata = EXCLUDED.metadata"
        )

        try:
            extras.execute_values(cur, insert_sql, rows, template="(%s, %s, %s, %s)")
            conn.commit()
            print(f"Added/updated {len(rows)} documents to table '{table_name}'")
        except Exception as e:
            conn.rollback()
            print("Failed to insert rows:", e)
    # Close DB resources
    try:
        cur.close()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass

    print("\nYou can now:")
    print("1. Run the Vector Inspector application")
    print(f"2. Connect to PgVector at {host}:{port}/{database} (table {table_name})")
    print(f"3. Select the '{table_name}' collection")
    print("4. Browse, search, and visualize the data!")


def create_sample_data_pinecone(
    api_key: str, index_name: str = "sample-documents", environment: str | None = None
):
    """Create sample data for Pinecone."""
    from pinecone import Pinecone, ServerlessSpec
    from sentence_transformers import SentenceTransformer
    import time

    print(f"Creating sample Pinecone data in index '{index_name}'...")

    # Initialize Pinecone
    pc = Pinecone(api_key=api_key)

    # Check if index exists
    existing_indexes = [idx.name for idx in pc.list_indexes()]

    if index_name not in existing_indexes:
        print(f"Creating new index '{index_name}'...")
        # Create index with 384 dimensions (all-MiniLM-L6-v2)
        pc.create_index(
            name=index_name,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )

        # Wait for index to be ready
        print("Waiting for index to be ready...")
        max_wait = 60
        start_time = time.time()
        while time.time() - start_time < max_wait:
            desc = pc.describe_index(index_name)
            status = (
                desc.status.get("state", "unknown")
                if hasattr(desc.status, "get")
                else str(desc.status)
            )  # type: ignore
            if status.lower() == "ready":
                break
            time.sleep(2)
        print(f"Index '{index_name}' is ready!")
    else:
        print(f"Using existing index '{index_name}'")

    # Get index
    index = pc.Index(index_name)

    documents, metadatas, ids = get_sample_docs()

    # Generate embeddings
    print("Generating embeddings with sentence-transformers (all-MiniLM-L6-v2)...")
    model = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = model.encode(documents, show_progress_bar=True).tolist()

    # Build vectors for Pinecone
    vectors = []
    for i in range(len(documents)):
        metadata = metadatas[i].copy()
        metadata["document"] = documents[i]  # Store document text in metadata
        metadata["_embedding_model"] = EMBEDDING_MODEL  # Store model used

        vectors.append({"id": ids[i], "values": embeddings[i], "metadata": metadata})

    # Upsert in batches of 100 (Pinecone limit)
    print(f"Upserting {len(vectors)} vectors to Pinecone...")
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        batch = vectors[i : i + batch_size]
        index.upsert(vectors=batch)
        print(f"  Upserted batch {i // batch_size + 1}/{(len(vectors) - 1) // batch_size + 1}")

    # Get stats
    stats = index.describe_index_stats()
    print(f"\nAdded {len(documents)} documents to index '{index_name}'")
    print(f"Index now contains {stats.get('total_vector_count', 0)} vectors")
    print("\nYou can now:")
    print("1. Run the Vector Inspector application")
    print("2. Connect to Pinecone with your API key")
    print(f"3. Select the '{index_name}' index")
    print("4. Browse, search, and visualize the data!")


def get_sample_docs():
    documents = [
        # Animals (15 docs)
        "The quick brown fox jumps over the lazy dog.",
        "Elephants are the largest land animals on Earth.",
        "Dolphins communicate using complex vocalizations.",
        "Cheetahs can run up to 70 miles per hour.",
        "Polar bears are excellent swimmers in Arctic waters.",
        "Hummingbirds can hover in mid-air by flapping their wings rapidly.",
        "Octopuses have three hearts and blue blood.",
        "Penguins huddle together to stay warm in Antarctica.",
        "Wolves hunt in coordinated packs for efficiency.",
        "Monarch butterflies migrate thousands of miles annually.",
        "Koalas sleep up to 22 hours per day.",
        "Giraffes have the same number of neck vertebrae as humans.",
        "Bats are the only mammals capable of sustained flight.",
        "Seahorses are the only species where males give birth.",
        "Owls can rotate their heads 270 degrees.",
        # Programming (20 docs)
        "Python is a high-level programming language.",
        "JavaScript runs in web browsers for interactive pages.",
        "TypeScript adds static typing to JavaScript.",
        "Rust ensures memory safety without garbage collection.",
        "Go was designed for concurrent programming at Google.",
        "C++ provides low-level memory manipulation capabilities.",
        "Java runs on the Java Virtual Machine.",
        "Swift is Apple's modern programming language.",
        "Ruby emphasizes programmer happiness and productivity.",
        "Kotlin is fully interoperable with Java code.",
        "Scala combines object-oriented and functional programming.",
        "Elixir runs on the Erlang virtual machine.",
        "PHP powers many content management systems.",
        "Perl excels at text processing and manipulation.",
        "R is designed for statistical computing and graphics.",
        "Julia achieves high performance for numerical computing.",
        "Haskell is a purely functional programming language.",
        "Clojure is a modern Lisp dialect for the JVM.",
        "Dart is optimized for building mobile applications.",
        "Lua is lightweight and embeddable in applications.",
        # AI & Machine Learning (25 docs)
        "Machine learning is a subset of artificial intelligence.",
        "Neural networks are inspired by the human brain.",
        "Deep learning uses multiple layers of neural networks.",
        "Convolutional neural networks excel at image recognition.",
        "Recurrent neural networks process sequential data effectively.",
        "Transformers revolutionized natural language processing.",
        "Reinforcement learning trains agents through rewards.",
        "Supervised learning requires labeled training data.",
        "Unsupervised learning finds patterns in unlabeled data.",
        "Transfer learning reuses pretrained model knowledge.",
        "Gradient descent optimizes neural network parameters.",
        "Backpropagation calculates gradients for training networks.",
        "Attention mechanisms help models focus on relevant information.",
        "GANs generate realistic synthetic data samples.",
        "Autoencoders learn compressed data representations.",
        "BERT uses bidirectional context for language understanding.",
        "GPT models generate coherent text sequences.",
        "Computer vision enables machines to interpret images.",
        "Natural language processing enables computers to understand text.",
        "Speech recognition converts audio to text transcriptions.",
        "Object detection identifies and locates objects in images.",
        "Sentiment analysis determines emotional tone of text.",
        "Named entity recognition extracts key information from text.",
        "Machine translation converts text between languages.",
        "Recommender systems suggest relevant items to users.",
        # Data Science (15 docs)
        "Data science involves extracting insights from data.",
        "Pandas provides powerful data manipulation tools.",
        "NumPy enables efficient numerical computing in Python.",
        "Matplotlib creates static and interactive visualizations.",
        "Scikit-learn offers simple machine learning algorithms.",
        "Data cleaning removes errors and inconsistencies.",
        "Feature engineering creates useful input variables.",
        "Cross-validation prevents overfitting in models.",
        "A/B testing compares different versions systematically.",
        "Time series analysis forecasts future values.",
        "Regression predicts continuous numerical outcomes.",
        "Classification assigns items to predefined categories.",
        "Clustering groups similar data points together.",
        "Dimensionality reduction simplifies high-dimensional data.",
        "Statistical inference draws conclusions from samples.",
        # Databases & Vectors (15 docs)
        "Vector databases store high-dimensional embeddings.",
        "Embeddings represent data in continuous vector spaces.",
        "Similarity search finds vectors close to a query vector.",
        "SQL databases use structured query language.",
        "NoSQL databases offer flexible schema designs.",
        "Graph databases model relationships between entities.",
        "Time-series databases optimize for temporal data.",
        "ACID properties ensure reliable database transactions.",
        "Indexing improves database query performance.",
        "Sharding distributes data across multiple servers.",
        "Replication creates data copies for availability.",
        "Normalization reduces data redundancy in tables.",
        "Denormalization optimizes for read performance.",
        "Vector similarity uses cosine or euclidean distance.",
        "Approximate nearest neighbor search speeds up retrieval.",
        # General Tech (10 docs)
        "Cloud computing provides on-demand computing resources.",
        "Microservices architecture splits applications into services.",
        "REST APIs enable communication between systems.",
        "GraphQL allows clients to request specific data.",
        "Docker containers package applications with dependencies.",
        "Kubernetes orchestrates containerized applications.",
        "CI/CD automates software testing and deployment.",
        "Version control tracks changes to source code.",
        "Agile methodology emphasizes iterative development.",
        "DevOps combines development and operations practices.",
    ]

    metadatas = [
        # Animals
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "marine"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "medium", "topic": "birds"},
        {"category": "animals", "length": "short", "topic": "marine"},
        {"category": "animals", "length": "short", "topic": "birds"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "insects"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "medium", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "mammals"},
        {"category": "animals", "length": "short", "topic": "marine"},
        {"category": "animals", "length": "short", "topic": "birds"},
        # Programming
        {"category": "programming", "length": "short", "topic": "languages"},
        {"category": "programming", "length": "short", "topic": "web"},
        {"category": "programming", "length": "short", "topic": "web"},
        {"category": "programming", "length": "short", "topic": "systems"},
        {"category": "programming", "length": "short", "topic": "systems"},
        {"category": "programming", "length": "short", "topic": "systems"},
        {"category": "programming", "length": "short", "topic": "languages"},
        {"category": "programming", "length": "short", "topic": "mobile"},
        {"category": "programming", "length": "short", "topic": "languages"},
        {"category": "programming", "length": "short", "topic": "languages"},
        {"category": "programming", "length": "short", "topic": "languages"},
        {"category": "programming", "length": "short", "topic": "functional"},
        {"category": "programming", "length": "short", "topic": "web"},
        {"category": "programming", "length": "short", "topic": "scripting"},
        {"category": "programming", "length": "short", "topic": "statistics"},
        {"category": "programming", "length": "short", "topic": "scientific"},
        {"category": "programming", "length": "short", "topic": "functional"},
        {"category": "programming", "length": "short", "topic": "functional"},
        {"category": "programming", "length": "short", "topic": "mobile"},
        {"category": "programming", "length": "short", "topic": "scripting"},
        # AI & ML
        {"category": "ai", "length": "short", "topic": "machine-learning"},
        {"category": "ai", "length": "short", "topic": "neural-networks"},
        {"category": "ai", "length": "short", "topic": "deep-learning"},
        {"category": "ai", "length": "short", "topic": "computer-vision"},
        {"category": "ai", "length": "short", "topic": "sequential"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "reinforcement"},
        {"category": "ai", "length": "short", "topic": "supervised"},
        {"category": "ai", "length": "short", "topic": "unsupervised"},
        {"category": "ai", "length": "short", "topic": "transfer-learning"},
        {"category": "ai", "length": "short", "topic": "optimization"},
        {"category": "ai", "length": "short", "topic": "training"},
        {"category": "ai", "length": "short", "topic": "architecture"},
        {"category": "ai", "length": "short", "topic": "generative"},
        {"category": "ai", "length": "short", "topic": "representation"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "computer-vision"},
        {"category": "ai", "length": "medium", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "speech"},
        {"category": "ai", "length": "short", "topic": "computer-vision"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "nlp"},
        {"category": "ai", "length": "short", "topic": "recommendation"},
        # Data Science
        {"category": "data", "length": "short", "topic": "overview"},
        {"category": "data", "length": "short", "topic": "tools"},
        {"category": "data", "length": "short", "topic": "tools"},
        {"category": "data", "length": "short", "topic": "visualization"},
        {"category": "data", "length": "short", "topic": "tools"},
        {"category": "data", "length": "short", "topic": "preprocessing"},
        {"category": "data", "length": "short", "topic": "engineering"},
        {"category": "data", "length": "short", "topic": "validation"},
        {"category": "data", "length": "short", "topic": "testing"},
        {"category": "data", "length": "short", "topic": "time-series"},
        {"category": "data", "length": "short", "topic": "regression"},
        {"category": "data", "length": "short", "topic": "classification"},
        {"category": "data", "length": "short", "topic": "clustering"},
        {"category": "data", "length": "short", "topic": "dimensionality"},
        {"category": "data", "length": "short", "topic": "statistics"},
        # Databases
        {"category": "databases", "length": "short", "topic": "vectors"},
        {"category": "vectors", "length": "short", "topic": "embeddings"},
        {"category": "vectors", "length": "short", "topic": "search"},
        {"category": "databases", "length": "short", "topic": "sql"},
        {"category": "databases", "length": "short", "topic": "nosql"},
        {"category": "databases", "length": "short", "topic": "graph"},
        {"category": "databases", "length": "short", "topic": "time-series"},
        {"category": "databases", "length": "short", "topic": "transactions"},
        {"category": "databases", "length": "short", "topic": "performance"},
        {"category": "databases", "length": "short", "topic": "scaling"},
        {"category": "databases", "length": "short", "topic": "availability"},
        {"category": "databases", "length": "short", "topic": "design"},
        {"category": "databases", "length": "short", "topic": "design"},
        {"category": "vectors", "length": "short", "topic": "similarity"},
        {"category": "vectors", "length": "short", "topic": "search"},
        # Tech
        {"category": "tech", "length": "short", "topic": "cloud"},
        {"category": "tech", "length": "short", "topic": "architecture"},
        {"category": "tech", "length": "short", "topic": "api"},
        {"category": "tech", "length": "short", "topic": "api"},
        {"category": "tech", "length": "short", "topic": "containers"},
        {"category": "tech", "length": "short", "topic": "orchestration"},
        {"category": "tech", "length": "short", "topic": "devops"},
        {"category": "tech", "length": "short", "topic": "tools"},
        {"category": "tech", "length": "short", "topic": "methodology"},
        {"category": "tech", "length": "short", "topic": "devops"},
    ]

    ids = [f"doc_{i}" for i in range(len(documents))]
    return documents, metadatas, ids


def main():
    parser = argparse.ArgumentParser(
        description="Create sample data for Vector Inspector.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  Create pgvector sample with flattened metadata (default):\n"
            "    python create_sample_data.py --provider pgvector --host localhost --port 5432 --database postgres --user postgres --password secret --name sample_documents\n\n"
            "  Create pgvector sample using JSONB metadata:\n"
            "    python create_sample_data.py --provider pgvector --host localhost --port 5432 --database postgres --user postgres --password secret --name sample_documents --no-flat-metadata\n\n"
            "Notes:\n"
            "  - By default the script creates explicit TEXT columns for metadata keys and simple indexes.\n"
            "  - Use --no-flat-metadata to keep metadata in a single JSONB column.\n"
        ),
    )
    parser.add_argument(
        "--provider",
        choices=["chroma", "qdrant", "pinecone", "pgvector"],
        default="chroma",
        help="Which vector DB to use",
    )
    parser.add_argument("--host", default="localhost", help="Qdrant host (for qdrant)")
    parser.add_argument("--port", type=int, default=6333, help="Qdrant port (for qdrant)")
    parser.add_argument(
        "--path", default=None, help="Local Qdrant DB path (if using embedded mode or chroma)"
    )
    parser.add_argument(
        "--database", default="postgres", help="Postgres database name (for pgvector)"
    )
    parser.add_argument("--user", default="postgres", help="Postgres user (for pgvector)")
    parser.add_argument("--password", default=None, help="Postgres password (for pgvector)")
    parser.add_argument(
        "--flat-metadata",
        dest="flat_metadata",
        action="store_true",
        help="Create explicit columns for metadata keys instead of JSONB (default)",
    )
    parser.add_argument(
        "--no-flat-metadata",
        dest="flat_metadata",
        action="store_false",
        help="Disable creating explicit metadata columns and use JSONB instead",
    )
    parser.set_defaults(flat_metadata=True)
    parser.add_argument(
        "--vector-size", type=int, default=384, help="Vector size for Qdrant collection"
    )
    parser.add_argument(
        "--name",
        default="sample_documents",
        help="Collection name (for chroma/qdrant) or index name (for pinecone)",
    )
    parser.add_argument(
        "--embedding-model", default=EMBEDDING_MODEL, help="Embedding model to use (for chroma)"
    )
    parser.add_argument("--api-key", default=None, help="Pinecone API key (for pinecone)")
    parser.add_argument(
        "--environment", default=None, help="Pinecone environment (for pinecone, optional)"
    )
    args = parser.parse_args()

    if args.provider == "chroma":
        create_sample_data_chroma(
            collection=args.name,
            path=args.path or "./chroma_data",
            embedding_model=args.embedding_model,
        )
    elif args.provider == "qdrant":
        create_sample_data_qdrant(
            host=args.host,
            port=args.port,
            collection_name=args.name,
            vector_size=args.vector_size,
            path=args.path,
        )
    elif args.provider == "pinecone":
        if not args.api_key:
            print("Error: --api-key is required for Pinecone provider")
            print("Usage: python create_sample_data.py --provider pinecone --api-key YOUR_API_KEY")
            sys.exit(1)
        create_sample_data_pinecone(
            api_key=args.api_key,
            index_name=args.name,
            environment=args.environment,
        )
    elif args.provider == "pgvector":
        create_sample_data_pgvector(
            host=args.host,
            port=args.port,
            database=args.database,
            user=args.user,
            password=args.password,
            table_name=args.name,
            vector_size=args.vector_size,
            flat_metadata=args.flat_metadata,
        )
    else:
        print("Unknown provider.")
        sys.exit(1)


if __name__ == "__main__":
    main()
