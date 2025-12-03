"""Retrieval node: Retrieve from RAG."""

from typing import Dict, Any
from ..state import AgentState
from ...services.keyword_search_service import keyword_search_service
from ...core.logging import setup_logging

logger = setup_logging(__name__)


def retrieve_from_rag(state: AgentState) -> Dict[str, Any]:
    """Retrieve relevant documents using keyword search.

    Fast keyword-based search with fuzzy matching (no GPU needed).

    Args:
        state: Current agent state

    Returns:
        Updated state with rag_context
    """
    # Use search_query (expanded query from extraction node)
    query = state.get("search_query", "")

    logger.info(f"Retrieve - searching for: '{query[:50]}...'")

    # Keyword search with fuzzy matching
    results = keyword_search_service.search(query, top_k=3)

    logger.info(f"Retrieve - found {len(results)} documents")

    return {
        "rag_context": results
    }
