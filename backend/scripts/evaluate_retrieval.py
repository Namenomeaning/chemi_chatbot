"""Evaluate local keyword retrieval on a small labeled set. No model calls or API keys."""

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))
from app.services.chunking import read_knowledge  # noqa: E402
from app.services.retrieval import keyword_search  # noqa: E402
from tests.fakes import FakeD1  # noqa: E402


async def main():
    db = FakeD1()
    for chunk in read_knowledge(ROOT / "knowledge"):
        await (
            db.prepare("INSERT INTO knowledge_fts(id,source,content) VALUES(?,?,?)")
            .bind(chunk["id"], chunk["source"], chunk["content"])
            .run()
        )
    cases = json.loads((ROOT / "tests/golden.json").read_text())
    hits = abstentions = positive = negative = 0
    results = []
    for case in cases:
        found = await keyword_search(db, case["query"], 3)
        if case["source"]:
            positive += 1
            correct = case["source"] in [row["source"] for row in found]
            hits += correct
        else:
            negative += 1
            correct = not found
            abstentions += correct
        results.append({**case, "passed": correct, "retrieved": [r["source"] for r in found]})
    report = {
        "scope": "local lexical retrieval only, small smoke set; not a production accuracy claim",
        "hit_rate_at_3": hits / positive,
        "abstention_accuracy": abstentions / negative,
        "cases": results,
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    if hits != positive or abstentions != negative:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
