"""Keyword-based search for chemistry compounds (no embeddings needed)."""

import json
from pathlib import Path
from typing import List, Dict, Any
from rapidfuzz import fuzz

from ..core.logging import setup_logging

logger = setup_logging(__name__)


class KeywordSearchService:
    """Fast keyword search using fuzzy matching."""

    def __init__(self, data_path: str = "data/chemistry_data.json"):
        self.compounds: List[Dict[str, Any]] = []
        self._load_data(data_path)

    def _load_data(self, data_path: str):
        """Load chemistry data."""
        path = Path(data_path)
        with open(path, 'r', encoding='utf-8') as f:
            self.compounds = json.load(f)
        logger.info(f"Loaded {len(self.compounds)} compounds")

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """Search compounds by name or formula.

        Args:
            query: Search query
            top_k: Number of results

        Returns:
            List of {**compound, 'score': float} dictionaries
        """
        query_lower = query.lower().strip()
        results = []

        for compound in self.compounds:
            # Search fields: IUPAC name and formula
            iupac_name = compound.get('iupac_name', '').lower()
            formula = compound.get('formula', '').lower()

            # Calculate similarity scores
            name_score = fuzz.token_sort_ratio(query_lower, iupac_name) / 100.0
            formula_score = fuzz.ratio(query_lower, formula) / 100.0

            # Take max score
            max_score = max(name_score, formula_score)

            if max_score >= 0.3:  # Threshold
                results.append({**compound, 'score': max_score})

        # Sort by score descending
        results.sort(key=lambda x: x['score'], reverse=True)

        logger.info(f"Search '{query}' → {len(results[:top_k])} results")
        return results[:top_k]


# Global instance
keyword_search_service = KeywordSearchService()
