"""Test keyword search service."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.services.keyword_search_service import keyword_search_service

print("="*80)
print("TESTING KEYWORD SEARCH SERVICE")
print("="*80)
print()

# Test cases
test_queries = [
    "Ethanol",
    "CH4",
    "C2H5OH",
    "Sodium",
    "Na",
    "Hydrogen",
    "methane",
    "etanol",  # Typo
    "Natri",   # Vietnamese
]

for query in test_queries:
    print(f"Query: '{query}'")
    print("-" * 80)

    results = keyword_search_service.search(query, top_k=3)

    if results:
        for i, result in enumerate(results, 1):
            print(f"  {i}. {result['iupac_name']} ({result['formula']}) - Score: {result['score']:.3f}")
    else:
        print("  No results found")

    print()

print("="*80)
print("✓ Test completed!")
