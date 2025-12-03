"""Test script to verify embedding service integration."""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.services import embedding_service

def test_embedding_service():
    """Test the embedding service."""
    print("=" * 60)
    print("Testing Embedding Service")
    print("=" * 60)

    # Load model
    print("\n1. Loading embedding model...")
    embedding_service.load_model()
    print(f"   ✓ Model loaded successfully")
    print(f"   Embedding dimension: {embedding_service.embedding_dim}")

    # Test single text encoding
    print("\n2. Testing single text encoding...")
    text = "Ethanol là ancol đơn chức bậc 1"
    embedding = embedding_service.encode(text)
    print(f"   Text: '{text}'")
    print(f"   ✓ Embedding generated: {len(embedding)} dimensions")

    # Test batch encoding
    print("\n3. Testing batch encoding...")
    texts = [
        "Ethanol",
        "Methane",
        "C2H5OH"
    ]
    embeddings = embedding_service.encode(texts)
    print(f"   Texts: {texts}")
    print(f"   ✓ Generated {len(embeddings)} embeddings")

    # Test similarity
    print("\n4. Testing similarity...")
    from numpy import dot
    from numpy.linalg import norm

    def cosine_similarity(a, b):
        return dot(a, b) / (norm(a) * norm(b))

    sim = cosine_similarity(embeddings[0], embeddings[2])
    print(f"   Similarity between 'Ethanol' and 'C2H5OH': {sim:.4f}")

    print("\n" + "=" * 60)
    print("✓ All tests passed!")
    print("=" * 60)

if __name__ == "__main__":
    test_embedding_service()
