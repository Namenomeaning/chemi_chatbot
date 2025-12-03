"""LangGraph workflow for chemistry chatbot."""

from typing import Literal
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from .state import AgentState
from .nodes import (
    rephrase_query,
    check_relevance,
    extract_and_validate,
    retrieve_from_rag,
    generate_response,
    check_relevance_route,
    check_validity_route
)


def build_graph():
    """Build the chemistry chatbot graph with checkpointer.

    Workflow:
        START → rephrase_query (handle "nó", "chất đó" with conversation context)
              → check_relevance (chemistry-related?)
                  ├─ if chemistry-related → extract_and_validate (expand keywords + validate)
                  │                       → retrieve_from_rag (ALWAYS - hybrid search handles typos)
                  │                       → generate_response (RAG for ID + LLM knowledge for answer)
                  │                       → END
                  └─ if not chemistry-related → END (with error message)

    Key Features:
    - Conversational: Uses conversation history to resolve pronouns ("nó" → "Hidro")
    - Flexible: Always proceeds to RAG retrieval (fuzzy search handles typos/variations)
    - Knowledge-based: Uses RAG to identify compound, LLM knowledge to answer questions
    - Minimal database: Only stores name, formula, type, image/audio paths (118 elements + 7 compounds)

    Returns:
        Compiled graph with MemorySaver checkpointer for conversation history
    """
    # Initialize graph
    workflow = StateGraph(AgentState)

    # Add nodes (2 Flash Lite nodes split from original Node 0)
    workflow.add_node("rephrase_query", rephrase_query)
    workflow.add_node("check_relevance", check_relevance)
    workflow.add_node("extract_and_validate", extract_and_validate)
    workflow.add_node("retrieve_from_rag", retrieve_from_rag)
    workflow.add_node("generate_response", generate_response)

    # Set entry point
    workflow.set_entry_point("rephrase_query")

    # Add normal edge from rephrase to relevance check
    workflow.add_edge("rephrase_query", "check_relevance")

    # Add conditional edges
    workflow.add_conditional_edges(
        "check_relevance",
        check_relevance_route,
        {
            "extract": "extract_and_validate",
            "end": END
        }
    )

    workflow.add_conditional_edges(
        "extract_and_validate",
        check_validity_route,
        {
            "retrieve": "retrieve_from_rag",
            "end": END
        }
    )

    # Add normal edges
    workflow.add_edge("retrieve_from_rag", "generate_response")
    workflow.add_edge("generate_response", END)

    # Compile with checkpointer for conversation history
    checkpointer = MemorySaver()
    return workflow.compile(checkpointer=checkpointer)


# Create global graph instance
graph = build_graph()
