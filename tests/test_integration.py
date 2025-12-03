"""Integration test for complete chatbot flow with new minimal schema."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(override=True)

from src.agent.graph import graph
from src.agent.state import AgentState
from src.services.embedding_service import embedding_service

# Load embedding model once
print("Loading embedding model...")
embedding_service.load_model()
print(f"✓ Model loaded (dim: {embedding_service.embedding_dim})\n")

# Test cases
test_cases = [
    {
        "name": "Basic query - Element name",
        "input": {"input_text": "Sodium là gì?"},
        "thread_id": "test-1"
    },
    {
        "name": "Follow-up with pronoun",
        "input": {"input_text": "Công thức của nó?"},
        "thread_id": "test-1"  # Same thread for context
    },
    {
        "name": "Knowledge question",
        "input": {"input_text": "Cấu hình electron của Hydrogen?"},
        "thread_id": "test-2"
    },
    {
        "name": "Formula search",
        "input": {"input_text": "C2H5OH"},
        "thread_id": "test-3"
    },
    {
        "name": "Typo handling",
        "input": {"input_text": "ethano"},  # Should find "ethanol" via fuzzy match
        "thread_id": "test-4"
    }
]

print("="*80)
print("INTEGRATION TEST - Chemistry Chatbot")
print("="*80)
print()

for i, test in enumerate(test_cases, 1):
    print(f"[{i}/{len(test_cases)}] {test['name']}")
    print("-" * 80)
    print(f"Input: {test['input']['input_text']}")

    try:
        # Invoke graph
        config = {"configurable": {"thread_id": test["thread_id"]}}
        result = graph.invoke(test["input"], config)

        # Check for errors
        if result.get("error_message"):
            print(f"❌ Error: {result['error_message']}")
        else:
            final_response = result.get("final_response", {})
            rag_context = result.get("rag_context", [])

            print(f"✅ Success")
            print(f"  Rephrased: {result.get('rephrased_query', 'N/A')}")
            print(f"  RAG docs: {len(rag_context)}")
            if rag_context:
                top = rag_context[0]
                print(f"  Top match: {top.get('iupac_name')} ({top.get('formula')}) - score: {top.get('score', 0):.3f}")
            print(f"  Response preview: {final_response.get('text_response', '')[:100]}...")
            print(f"  Has image: {bool(final_response.get('image_path'))}")
            print(f"  Has audio: {bool(final_response.get('audio_path'))}")

    except Exception as e:
        print(f"❌ Exception: {str(e)}")
        import traceback
        traceback.print_exc()

    print("\n" + "="*80 + "\n")

print("✓ Integration test complete!")
