"""Embedding service using local Qwen3 model."""

import os
from pathlib import Path
from typing import List, Union
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

from ..core.logging import setup_logging

load_dotenv(override=True)
logger = setup_logging(__name__)


class EmbeddingService:
    """Service for generating embeddings using local Qwen3 model."""

    def __init__(self):
        """Initialize the embedding service with lazy loading."""
        self._model = None
        self._model_path = None
        self._embedding_dim = None

    def load_model(self, model_path: str = None) -> None:
        """Load the embedding model from local directory.

        Args:
            model_path: Path to local model directory. If None, uses default from project structure.
        """
        if model_path is None:
            # Default to project models directory
            project_root = Path(__file__).parent.parent.parent
            model_path = project_root / "models" / "embedding" / "qwen3-embedding-0.6b"

        self._model_path = str(model_path)

        logger.info(f"Loading embedding model from {self._model_path}...")
        self._model = SentenceTransformer(self._model_path)

        # Get embedding dimension
        self._embedding_dim = self._model.get_sentence_embedding_dimension()

        logger.info(f"✓ Embedding model loaded successfully (dim: {self._embedding_dim})")

    @property
    def model(self) -> SentenceTransformer:
        """Get the loaded model, raise error if not loaded."""
        if self._model is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        return self._model

    @property
    def embedding_dim(self) -> int:
        """Get embedding dimension."""
        if self._embedding_dim is None:
            raise RuntimeError("Embedding model not loaded. Call load_model() first.")
        return self._embedding_dim

    def encode(
        self,
        texts: Union[str, List[str]],
        batch_size: int = 32,
        show_progress_bar: bool = False,
        normalize_embeddings: bool = True
    ) -> List[List[float]]:
        """Generate embeddings for text(s).

        Args:
            texts: Single text or list of texts
            batch_size: Batch size for encoding
            show_progress_bar: Whether to show progress bar
            normalize_embeddings: Whether to normalize embeddings (recommended for cosine similarity)

        Returns:
            List of embeddings (each embedding is a list of floats)
        """
        # Convert single string to list
        is_single = isinstance(texts, str)
        if is_single:
            texts = [texts]

        # Generate embeddings
        embeddings = self.model.encode(
            texts,
            batch_size=batch_size,
            show_progress_bar=show_progress_bar,
            normalize_embeddings=normalize_embeddings,
            convert_to_numpy=True
        )

        # Convert to list of lists
        embeddings_list = embeddings.tolist()

        # Return single embedding if input was single string
        if is_single:
            return embeddings_list[0]

        return embeddings_list


# Global instance
embedding_service = EmbeddingService()
