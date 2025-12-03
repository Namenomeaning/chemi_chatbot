"""Test optimized extract_validate with keyword search."""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
load_dotenv(override=True)

from src.agent.nodes.extract_validate import extract_and_validate

print("="*80)
print("TEST OPTIMIZED EXTRACT & VALIDATE")
print("="*80)
print()

# Test cases
test_cases = [
    {"input": "Natri là gì?", "expected": "Sodium"},
    {"input": "CH4", "expected": "CH4"},
    {"input": "Ethanol", "expected": "Ethanol"},
    {"input": "C2H5OH", "expected": "C2H5OH"},
    {"input": "Hydro", "expected": "Hydrogen"},
    {"input": "Metan", "expected": "Methane"},
    {"input": "Rượu etylic", "expected": "Ethanol"},
    {"input": "Na", "expected": "Na"},
]

for test in test_cases:
    state = {"rephrased_query": test["input"]}

    print(f"Input: '{test['input']}'")
    print(f"Expected: '{test['expected']}'")

    result = extract_and_validate(state)
    search_query = result.get("search_query", "")
    is_valid = result.get("is_valid", False)

    # Check if result is good
    match = test["expected"].lower() in search_query.lower()
    status = "✅" if match else "❌"

    print(f"Result: '{search_query}' (valid={is_valid}) {status}")
    print("-" * 80)
    print()

print("="*80)
print("✓ Test completed!")
