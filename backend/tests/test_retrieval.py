import pytest

from app.core.config import Settings
from app.services.chunking import chunk_document
from app.services.retrieval import filter_citations, keyword_expression, reciprocal_rank_fusion, retrieve
from tests.fakes import FakeD1


def test_chunk_ids_and_overlap_are_deterministic():
    chunks = chunk_document("source", "abcdefghij", size=6, overlap=2)
    assert [c["content"] for c in chunks] == ["abcdef", "efghij"]
    assert chunks == chunk_document("source", "abcdefghij", size=6, overlap=2)


def test_rrf_combines_rankings_and_citations_are_filtered():
    assert reciprocal_rank_fusion([["a", "b"], ["b", "c"]])[0] == "b"
    text, citations = filter_citations("Fact [source:a] forged [source:unknown]", [{"id": "a", "source": "notes.md"}])
    assert "unknown" not in text
    assert citations == [{"id": "a", "source": "notes.md"}]
    assert keyword_expression('" OR *') == '"or"'


@pytest.mark.asyncio
async def test_hybrid_retrieval_and_threshold():
    db = FakeD1()
    for key, content in [("a", "Ethanol is an alcohol."), ("b", "Methane is an alkane.")]:
        await (
            db.prepare("INSERT INTO knowledge_fts(id,source,content) VALUES(?,?,?)")
            .bind(key, key + ".md", content)
            .run()
        )

    class AI:
        async def run(self, model, options):
            return {"data": [[0.1] * 768]}

    class Vectors:
        async def query(self, embedding, options):
            return {"matches": [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.2}]}

    settings = Settings(openrouter_api_key="fake")
    found = await retrieve(db, AI(), Vectors(), settings, "ethanol")
    assert [r["id"] for r in found] == ["a"]
    assert await retrieve(db, None, None, settings, "astronauts") == []


def test_no_evidence_abstains_without_calling_model(client, env, monkeypatch):
    env.RAG_ENABLED = "true"

    def forbidden(*args):
        raise AssertionError("A model must not run without evidence")

    monkeypatch.setattr("app.services.query.build_agent", forbidden)
    response = client.post("/query", json={"text": "astronauts"}, headers={"X-API-Key": "test-access-key"})
    assert response.status_code == 200
    assert response.json()["abstained"] is True
