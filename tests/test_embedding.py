"""Simple test script for Qwen3 embedding model."""

from pathlib import Path
from sentence_transformers import SentenceTransformer

# Model path
MODEL_PATH = Path(__file__).parent / "models" / "embedding" / "qwen3-embedding-0.6b"

# Sample chemistry texts (Vietnamese and English)
texts = [
    "Ethanol là ancol đơn chức bậc 1, chất lỏng không màu, tan vô hạn trong nước.",
    "Ethanol is a primary alcohol with the formula C2H5OH.",
    "C2H5OH",
    "Methane is a hydrocarbon with the formula CH4.",
    "Metan là hydrocarbon đơn giản nhất với công thức CH4.",
]

# Load the model
print(f"Loading embedding model from {MODEL_PATH}...")
model = SentenceTransformer(str(MODEL_PATH))

# Generate embeddings
print(f"\nGenerating embeddings for {len(texts)} texts...")
embeddings = model.encode(texts, show_progress_bar=True)

print(f"\n✓ Embeddings generated successfully!")
print(f"  Model dimension: {embeddings.shape[1]}")
print(f"  Number of embeddings: {embeddings.shape[0]}")
print(f"  Embedding shape: {embeddings.shape}")

# Calculate similarity between Vietnamese and English descriptions of ethanol
from numpy import dot
from numpy.linalg import norm

def cosine_similarity(a, b):
    return dot(a, b) / (norm(a) * norm(b))

print("\nSimilarity scores:")
print(f"  Vietnamese Ethanol vs English Ethanol: {cosine_similarity(embeddings[0], embeddings[1]):.4f}")
print(f"  Ethanol (Vietnamese) vs C2H5OH (formula): {cosine_similarity(embeddings[0], embeddings[2]):.4f}")
print(f"  Ethanol (English) vs Methane (English): {cosine_similarity(embeddings[1], embeddings[3]):.4f}")
print(f"  Methane (English) vs Methane (Vietnamese): {cosine_similarity(embeddings[3], embeddings[4]):.4f}")
print("\nDone!")
