"""Qdrant search service with optimized hybrid search for chemistry queries."""

import os
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from qdrant_client import QdrantClient, models

from ..core.logging import setup_logging
from .embedding_service import embedding_service

load_dotenv(override=True)
logger = setup_logging(__name__)


class QdrantService:
    """Optimized service class for chemistry compound hybrid search.

    Uses RRF (Reciprocal Rank Fusion) to combine:
    - Dense vectors (Qwen2.5 embeddings) for semantic search
    - Sparse vectors (BM25) for exact formula/name matching
    """

    def __init__(self):
        """Initialize Qdrant client."""
        self.host = os.getenv("QDRANT_HOST", "localhost")
        self.port = int(os.getenv("QDRANT_PORT", "6333"))
        self.collection_name = os.getenv("QDRANT_COLLECTION_NAME", "chemistry_compounds")
        self.top_k = int(os.getenv("RAG_TOP_K", "3"))
        self.score_threshold = float(os.getenv("RAG_SCORE_THRESHOLD", "0.3"))

        self.client = QdrantClient(
            host=self.host,
            port=self.port,
            check_compatibility=False
        )
        logger.info(f"Qdrant service initialized: {self.host}:{self.port} (collection: {self.collection_name})")

    def preprocess_query(self, query: str) -> str:
        """Normalize query for better retrieval.

        Args:
            query: Raw user query

        Returns:
            Preprocessed query string
        """
        # Trim whitespace
        query = query.strip()

        # Common abbreviation expansion (optional)
        expansions = {
            "NaCl": "sodium chloride",
            "HCl": "hydrogen chloride",
            "H2O": "water",
        }
        if query in expansions:
            logger.debug(f"Query expanded: '{query}' → '{expansions[query]}'")
            return expansions[query]

        return query

    def hybrid_search(self, query: str, limit: Optional[int] = None, threshold: Optional[float] = None) -> List[Dict[str, Any]]:
        """Perform optimized hybrid search with RRF fusion.

        Based on test results:
        - Perfect matches (exact name/formula) achieve score ~1.0
        - Good semantic matches achieve score 0.7-0.9
        - Related items achieve score 0.3-0.6

        Args:
            query: Search query text (name or formula)
            limit: Number of results to return (default: 3 from env)
            threshold: Minimum score threshold (default: 0.3 from env)

        Returns:
            List of results with payload + score, sorted by relevance
        """
        if limit is None:
            limit = self.top_k
        if threshold is None:
            threshold = self.score_threshold

        # Preprocess query
        processed_query = self.preprocess_query(query)
        logger.debug(f"Search query: '{query}' (processed: '{processed_query}'), limit={limit}, threshold={threshold}")

        try:
            # Generate dense embedding using local Qwen2.5 model
            query_embedding = embedding_service.encode(processed_query)

            # Hybrid search with RRF fusion (optimized based on tests)
            results = self.client.query_points(
                collection_name=self.collection_name,
                prefetch=[
                    # Dense vector search (semantic understanding)
                    models.Prefetch(
                        query=query_embedding,
                        using="dense",
                        limit=limit * 2  # Prefetch 2x for better fusion
                    ),
                    # Sparse BM25 search (exact formula/name matching)
                    models.Prefetch(
                        query=models.Document(
                            text=processed_query,
                            model="Qdrant/bm25"
                        ),
                        using="sparse",
                        limit=limit * 2
                    )
                ],
                query=models.FusionQuery(
                    fusion=models.Fusion.RRF  # Reciprocal Rank Fusion
                ),
                limit=limit,
                with_payload=True
            )

            # Extract payloads with scores, filter by threshold
            filtered_results = [
                {**point.payload, "score": point.score}
                for point in results.points
                if point.score >= threshold
            ]

            top_score = filtered_results[0]['score'] if filtered_results else 0.0
            logger.info(
                f"Search complete: query='{query}' → {len(filtered_results)}/{len(results.points)} results "
                f"(threshold={threshold}, top_score={top_score:.4f})"
            )
            return filtered_results

        except Exception as e:
            logger.error(f"Hybrid search failed for query='{query}': {str(e)}")
            return []

    def search_with_context(self, query: str) -> Dict[str, Any]:
        """Search with structured context for LLM integration.

        Returns top match + related items in a format optimized for RAG.

        Args:
            query: Search query (name or formula)

        Returns:
            Dict with 'found', 'primary' (best match), 'related' (similar items)
        """
        results = self.hybrid_search(query, limit=self.top_k, threshold=self.score_threshold)

        if not results:
            logger.warning(f"No results found for query: '{query}'")
            return {
                "found": False,
                "message": "Không tìm thấy thông tin trong cơ sở dữ liệu",
                "query": query
            }

        # Primary result (best match)
        primary = results[0]

        # Related results (if any)
        related = [
            {
                "name": r["iupac_name"],
                "formula": r["formula"],
                "type": r["type"],
                "score": r["score"]
            }
            for r in results[1:]
        ]

        logger.info(
            f"Context prepared: primary='{primary['iupac_name']}' (score={primary['score']:.4f}), "
            f"related={len(related)}"
        )

        return {
            "found": True,
            "query": query,
            "primary": {
                "doc_id": primary["doc_id"],
                "name": primary["iupac_name"],
                "formula": primary["formula"],
                "type": primary["type"],
                "image_path": primary["image_path"],
                "audio_path": primary["audio_path"],
                "confidence": primary["score"]
            },
            "related": related,
            "total_results": len(results)
        }


# Global instance
qdrant_service = QdrantService()
