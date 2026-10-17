import json

import httpx
import pytest

from app.core.config import Settings
from app.tools.factory import make_tools
from tests.fakes import FakeR2


@pytest.mark.asyncio
async def test_provider_artifacts_and_pubchem_fallback(monkeypatch):
    requests = []
    quiz = {
        "question_text": "Which is an alcohol?",
        "options": ["A) Ethanol", "B) Methane"],
        "correct_answer": "A",
        "explanation": "Ethanol has a hydroxyl group.",
    }

    def respond(request):
        requests.append(request)
        if request.url.path.endswith("cids/JSON"):
            return httpx.Response(200, json={"IdentifierList": {"CID": [702]}})
        if request.url.path.endswith("/audio/speech"):
            return httpx.Response(200, content=b"mp3-bytes")
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(quiz)}}]})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.tools.factory.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(respond), **kwargs),
    )
    bucket = FakeR2()
    tools = {tool.name: tool for tool in make_tools(Settings(openrouter_api_key="private-key"), bucket)}
    for name, args, kind in [
        ("search_image", {"keyword": "ethanol structure"}, "image"),
        ("generate_speech", {"text": "Ethanol"}, "audio"),
        ("generate_quiz", {"question_type": "mcq", "topic": "alcohol", "level": 1}, "quiz"),
    ]:
        result = await tools[name].ainvoke({"name": name, "args": args, "id": name, "type": "tool_call"})
        assert result.artifact["kind"] == kind
        if kind == "audio":
            assert bucket.objects[result.artifact["key"]] == b"mp3-bytes"
        if kind == "quiz":
            assert result.artifact["data"]["correct_answer"] == "A"
    assert len(requests) == 3


@pytest.mark.asyncio
async def test_provider_failure_does_not_expose_credentials(monkeypatch, caplog):
    def reject(request):
        return httpx.Response(403, json={"error": "private-key"})

    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.tools.factory.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(reject), **kwargs),
    )
    tools = make_tools(Settings(openrouter_api_key="private-key", serpapi_key="private-key"), FakeR2())
    result = await tools[0].ainvoke(
        {"name": "search_image", "args": {"keyword": "ethanol"}, "id": "1", "type": "tool_call"}
    )
    assert result.artifact is None
    assert "private-key" not in result.content
    assert "private-key" not in caplog.text
