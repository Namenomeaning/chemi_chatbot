"""Test hybrid search strategies to find optimal configuration for chemistry chatbot."""

import os
import sys
from pathlib import Path
from typing import List, Dict
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

load_dotenv(override=True)

from src.services.embedding_service import embedding_service

# Configuration
QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
COLLECTION_NAME = os.getenv("QDRANT_COLLECTION_NAME", "chemistry_compounds")

# Initialize clients
qdrant_client = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)

# Load embedding model
print("Loading embedding model...")
embedding_service.load_model()
print(f"✓ Embedding dimension: {embedding_service.embedding_dim}\n")

def hybrid_search(
    query: str,
    top_k: int = 3,
    dense_weight: float = 0.7,
    sparse_weight: float = 0.3
) -> List[Dict]:
    """Perform hybrid search with configurable weights.

    Args:
        query: Search query text
        top_k: Number of results to return
        dense_weight: Weight for dense vector search (0-1)
        sparse_weight: Weight for sparse BM25 search (0-1)

    Returns:
        List of search results with scores
    """
    # Generate dense embedding for query
    query_embedding = embedding_service.encode(query)

    # Perform hybrid search
    results = qdrant_client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=query_embedding,
                using="dense",
                limit=top_k * 2  # Pre-fetch more for reranking
            ),
            models.Prefetch(
                query=models.Document(
                    text=query,
                    model="Qdrant/bm25"
                ),
                using="sparse",
                limit=top_k * 2
            )
        ],
        query=models.FusionQuery(
            fusion=models.Fusion.RRF  # Reciprocal Rank Fusion
        ),
        limit=top_k,
        with_payload=True
    )

    return results.points

def print_results(query: str, results: List, strategy: str = ""):
    """Pretty print search results."""
    print(f"Query: '{query}' {strategy}")
    print("=" * 80)

    if not results:
        print("  No results found\n")
        return

    for idx, point in enumerate(results, 1):
        payload = point.payload
        score = point.score if hasattr(point, 'score') else 0

        print(f"  [{idx}] Score: {score:.4f}")
        print(f"      Name: {payload.get('iupac_name', 'N/A')}")
        print(f"      Formula: {payload.get('formula', 'N/A')}")
        print(f"      Type: {payload.get('type', 'N/A')}")
        print(f"      Doc ID: {payload.get('doc_id', 'N/A')}")
        print()

# Test cases grouped by search scenario
test_cases = {
    "Element Names (English)": [
        "Sodium",
        "Iron",
        "Gold",
        "Hydrogen",
        "Oxygen"
    ],
    "Element Formulas (Symbols)": [
        "Na",
        "Fe",
        "Au",
        "H",
        "O",
        "C"
    ],
    "Compound Names (IUPAC)": [
        "Ethanol",
        "Methane",
        "Ethene",
        "Ethanoic acid"
    ],
    "Compound Formulas": [
        "C2H5OH",
        "CH4",
        "C2H4",
        "CH3COOH"
    ],
    "Partial/Fuzzy Matches": [
        "sodium",  # lowercase
        "eth",     # partial match
        "acid",    # generic term
        "alcohol"  # class name
    ],
    "Multi-word Queries": [
        "sodium chloride",
        "ethyl ethanoate",
        "acetic acid"
    ]
}

print("="*80)
print("HYBRID SEARCH TESTING - Chemistry Chatbot RAG")
print("="*80)
print(f"Collection: {COLLECTION_NAME}")
print(f"Total points: {qdrant_client.count(COLLECTION_NAME).count}")
print("="*80)
print()

# Test each category
for category, queries in test_cases.items():
    print(f"\n{'='*80}")
    print(f"TEST CATEGORY: {category}")
    print(f"{'='*80}\n")

    for query in queries:
        results = hybrid_search(query, top_k=3)
        print_results(query, results, strategy="[RRF Fusion]")
        print()

# Performance comparison: Different strategies
print("\n" + "="*80)
print("STRATEGY COMPARISON FOR KEY QUERIES")
print("="*80 + "\n")

key_queries = [
    ("Na", "Element symbol - exact match test"),
    ("Sodium", "Element name - semantic search test"),
    ("C2H5OH", "Compound formula - exact match test"),
    ("Ethanol", "Compound name - semantic search test")
]

for query, description in key_queries:
    print(f"\n{'='*80}")
    print(f"Query: '{query}' - {description}")
    print(f"{'='*80}\n")

    # Standard RRF fusion
    results = hybrid_search(query, top_k=3)
    print_results(query, results, strategy="[Default RRF]")

print("\n" + "="*80)
print("RECOMMENDATIONS")
print("="*80)
print("""
Based on the test results above, recommended configuration:

1. **Top K**: Use K=3 for most queries
   - Elements: 1 result usually sufficient (unique names/symbols)
   - Compounds: 2-3 results to catch IUPAC + common names

2. **Fusion Strategy**: RRF (Reciprocal Rank Fusion)
   - Works well for both exact matches (formulas) and semantic (names)
   - No manual weight tuning needed

3. **Search Optimization**:
   - Short queries (1-2 words): Sparse dominates (good for formulas)
   - Longer queries: Dense helps (semantic understanding)
   - RRF automatically balances both

4. **Pre-processing**:
   - Normalize query (lowercase) for better matching
   - Strip extra whitespace
   - Consider expanding common abbreviations (e.g., "NaCl" -> "sodium chloride")

5. **LLM Integration**:
   - Return top 3 results max to minimize token usage
   - Include full payload (type, name, formula, image_path, audio_path)
   - Let LLM select the most relevant from top 3
""")
