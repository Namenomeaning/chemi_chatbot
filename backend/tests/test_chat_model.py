import json

import httpx
import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from app.core.config import Settings
from app.core.errors import ModelUnavailable
from app.services.agent import build_agent, run_agent
from app.services.chat_model import OpenRouterChat
from app.services.d1_saver import D1Saver
from app.tools.factory import make_tools
from tests.fakes import FakeD1, FakeR2


def mock_http(monkeypatch, handler):
    real_client = httpx.AsyncClient
    monkeypatch.setattr(
        "app.services.chat_model.httpx.AsyncClient",
        lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs),
    )


@pytest.mark.asyncio
async def test_adapter_preserves_multimodal_input_and_usage(monkeypatch):
    seen = []

    def respond(request):
        seen.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "Ethanol"}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            },
        )

    mock_http(monkeypatch, respond)
    model = OpenRouterChat(api_key="test-key", model="test-model")
    content = [
        {"type": "text", "text": "Identify this"},
        {"type": "image_url", "image_url": {"url": "data:image/png;base64,abc"}},
    ]
    result = await model.ainvoke([SystemMessage(content="Tutor"), HumanMessage(content=content)])
    assert seen[0]["messages"][1]["content"] == content
    assert result.usage_metadata["total_tokens"] == 12
    assert result.content == "Ethanol"


@pytest.mark.asyncio
async def test_full_graph_executes_tool_and_sends_tool_result_to_model(monkeypatch):
    seen = []

    def respond(request):
        if request.url.path.endswith("cids/JSON"):
            return httpx.Response(200, json={"IdentifierList": {"CID": [702]}})
        body = json.loads(request.content)
        seen.append(body)
        if not any(message["role"] == "tool" for message in body["messages"]):
            message = {
                "content": None,
                "tool_calls": [
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {"name": "search_image", "arguments": '{"keyword":"ethanol structure"}'},
                    }
                ],
            }
        else:
            message = {"content": "Ethanol is an alcohol."}
        return httpx.Response(200, json={"choices": [{"message": message}]})

    mock_http(monkeypatch, respond)
    settings = Settings(openrouter_api_key="test-key")
    agent = build_agent(settings, D1Saver(FakeD1()), make_tools(settings, FakeR2()))
    result = await run_agent(agent, [{"role": "user", "content": "Ethanol?"}], "test-thread")
    assert result["messages"][-1].content == "Ethanol is an alcohol."
    assert len(seen) == 2
    assert seen[1]["messages"][-1]["tool_call_id"] == "call-1"
    assert any(m.type == "tool" and m.artifact["kind"] == "image" for m in result["messages"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(503, json={"error": "secret"}),
        httpx.Response(200, json={"choices": []}),
        httpx.Response(
            200,
            json={
                "choices": [{"message": {"tool_calls": [{"id": "1", "function": {"name": "tool", "arguments": "[]"}}]}}]
            },
        ),
    ],
)
async def test_invalid_provider_response_is_application_error(monkeypatch, response):
    mock_http(monkeypatch, lambda request: response)
    with pytest.raises(ModelUnavailable):
        await OpenRouterChat(api_key="test-key", model="test-model").ainvoke("hello")
