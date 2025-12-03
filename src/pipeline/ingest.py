"""Ingest chemistry data (elements + compounds) into Qdrant with hybrid search (dense + sparse vectors)."""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

# Add project root to path for direct script execution
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(override=True)

# Import embedding service
from src.services.embedding_service import embedding_service

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "chemistry_compounds")
DATA_FILE = project_root / "data" / "chemistry_data.json"

# Initialize Qdrant client
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT, check_compatibility=False)

def create_collection():
    """Create Qdrant collection with hybrid search configuration."""
    # Check if collection exists
    collections = qdrant_client.get_collections().collections
    collection_exists = any(c.name == COLLECTION_NAME for c in collections)

    if collection_exists:
        print(f"Collection '{COLLECTION_NAME}' already exists. Deleting...")
        qdrant_client.delete_collection(COLLECTION_NAME)

    # Get embedding dimension from loaded model
    embedding_dim = embedding_service.embedding_dim
    print(f"Using embedding dimension: {embedding_dim}")

    # Create collection with dense + sparse vectors
    qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=embedding_dim,
                distance=models.Distance.COSINE
            )
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF
            )
        }
    )
    print(f"Created collection '{COLLECTION_NAME}' with hybrid search enabled")

def load_chemistry_documents() -> List[Dict]:
    """Load all chemistry documents (elements + compounds) from JSON file."""
    print(f"Loading chemistry data from {DATA_FILE}...")

    if not DATA_FILE.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_FILE}")

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        documents = json.load(f)

    elements = [d for d in documents if d["type"] == "element"]
    compounds = [d for d in documents if d["type"] == "compound"]

    print(f"Loaded {len(documents)} items ({len(elements)} elements, {len(compounds)} compounds)")
    return documents

def create_searchable_text(doc: Dict) -> str:
    """Create searchable text from available fields in minimal schema.

    Minimal schema fields:
    - type (element/compound)
    - doc_id
    - iupac_name (English name for elements, IUPAC name for compounds)
    - formula (symbol for elements, molecular formula for compounds)
    - image_path (URL or local path)
    - audio_path (local WAV file)
    """
    # Combine IUPAC name and formula for search
    # This allows searching by name OR formula
    text_parts = [
        doc.get("iupac_name", ""),
        doc.get("formula", ""),
        doc.get("type", ""),  # Include type for filtering
        doc.get("doc_id", "")  # Include doc_id for exact matching
    ]
    return " ".join(filter(None, text_parts))

def ingest_documents(documents: List[Dict]):
    """Ingest documents into Qdrant with hybrid vectors using local embeddings."""
    # Prepare all searchable texts
    searchable_texts = [create_searchable_text(doc) for doc in documents]

    # Generate embeddings in batch using local Qwen2.5 model
    print(f"\nGenerating embeddings for {len(documents)} documents...")
    dense_embeddings = embedding_service.encode(
        searchable_texts,
        batch_size=32,
        show_progress_bar=True
    )

    # Create points
    points = []
    for idx, (doc, dense_embedding) in enumerate(zip(documents, dense_embeddings)):
        searchable_text = searchable_texts[idx]

        # Create point with local dense embeddings and BM25 sparse
        point = models.PointStruct(
            id=idx,
            vector={
                "dense": dense_embedding,
                "sparse": models.Document(
                    text=searchable_text,
                    model="Qdrant/bm25"
                )
            },
            payload=doc
        )
        points.append(point)

        # Progress output
        item_type = doc.get("type", "unknown")
        print(f"  [{idx+1}/{len(documents)}] {doc['iupac_name']} ({item_type})")

    # Upload to Qdrant
    print(f"\nUploading {len(points)} points to Qdrant...")
    qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )
    print(f"✓ Uploaded {len(points)} points to Qdrant")

def main():
    """Main ingestion workflow."""
    print("="*60)
    print("Chemistry Data Ingestion - Hybrid Search (Dense + Sparse)")
    print("="*60)

    # Step 1: Load embedding model
    print("\n[1/4] Loading embedding model...")
    embedding_service.load_model()
    print(f"  Embedding dimension: {embedding_service.embedding_dim}")

    # Step 2: Create collection
    print("\n[2/4] Creating Qdrant collection...")
    create_collection()

    # Step 3: Load documents
    print("\n[3/4] Loading chemistry data...")
    documents = load_chemistry_documents()

    # Step 4: Ingest documents
    print("\n[4/4] Ingesting documents with embeddings...")
    ingest_documents(documents)

    # Verify
    print("\n" + "="*60)
    print("Verification")
    print("="*60)
    collection_info = qdrant_client.get_collection(COLLECTION_NAME)
    print(f"Collection: {COLLECTION_NAME}")
    print(f"Points count: {collection_info.points_count}")
    print(f"Vectors config: {collection_info.config.params.vectors}")
    print(f"Sparse vectors: {collection_info.config.params.sparse_vectors}")

    print("\n✓ Ingestion complete!")

if __name__ == "__main__":
    main()
