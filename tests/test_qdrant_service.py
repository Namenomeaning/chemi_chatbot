"""Test the optimized Qdrant service."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(override=True)

from src.services.embedding_service import embedding_service
from src.services.qdrant_service import qdrant_service

# Load embedding model
print("Loading embedding model...")
embedding_service.load_model()
print(f"✓ Model loaded (dim: {embedding_service.embedding_dim})\n")

# Test queries
test_queries = [
    ("Sodium", "Element name test"),
    ("Na", "Element symbol test"),
    ("Ethanol", "Compound name test"),
    ("C2H5OH", "Compound formula test"),
    ("sodium chloride", "Multi-word compound test"),
    ("acetic acid", "Common name test"),
]

print("="*80)
print("TESTING OPTIMIZED QDRANT SERVICE")
print("="*80)
print()

for query, description in test_queries:
    print(f"Query: '{query}' ({description})")
    print("-" * 80)

    # Test hybrid_search (raw results)
    results = qdrant_service.hybrid_search(query, limit=3)
    print(f"hybrid_search() returned {len(results)} results:")
    for i, r in enumerate(results[:3], 1):
        print(f"  [{i}] {r['iupac_name']} ({r['formula']}) - score: {r['score']:.4f}")

    # Test search_with_context (structured for LLM)
    context = qdrant_service.search_with_context(query)
    if context["found"]:
        primary = context["primary"]
        print(f"\nsearch_with_context():")
        print(f"  Primary: {primary['name']} ({primary['formula']})")
        print(f"  Type: {primary['type']}")
        print(f"  Confidence: {primary['confidence']:.4f}")
        print(f"  Image: {primary['image_path'][:60]}...")
        print(f"  Audio: {primary['audio_path']}")
        if context["related"]:
            print(f"  Related: {len(context['related'])} items")
    else:
        print(f"  Not found: {context['message']}")

    print("\n" + "="*80 + "\n")

print("\n✓ All tests completed successfully!")
