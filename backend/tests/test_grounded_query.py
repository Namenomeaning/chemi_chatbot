from langchain_core.messages import AIMessage, HumanMessage

from tests.test_errors_and_api import HEADERS


def test_grounded_answer_keeps_only_retrieved_citations(client, env, monkeypatch):
    env.RAG_ENABLED = "true"

    async def retrieved(*args):
        return [{"id": "known", "source": "notes.md", "content": "Ethanol is an alcohol."}]

    class Agent:
        async def ainvoke(self, payload, config):
            return {
                "messages": [HumanMessage(content="ethanol"), AIMessage(content="Fact [source:known] [source:forged]")]
            }

    monkeypatch.setattr("app.services.query.retrieve", retrieved)
    monkeypatch.setattr("app.services.query.build_agent", lambda *args, **kwargs: Agent())
    response = client.post("/query", json={"text": "ethanol"}, headers=HEADERS)
    assert response.status_code == 200
    assert response.json()["citations"] == [{"id": "known", "source": "notes.md"}]
    assert "forged" not in response.json()["text_response"]


def test_uncited_grounded_answer_abstains(client, env, monkeypatch):
    env.RAG_ENABLED = "true"

    async def retrieved(*args):
        return [{"id": "known", "source": "notes.md", "content": "Ethanol is an alcohol."}]

    class Agent:
        async def ainvoke(self, payload, config):
            return {"messages": [HumanMessage(content="ethanol"), AIMessage(content="Unsupported answer")]}

    monkeypatch.setattr("app.services.query.retrieve", retrieved)
    monkeypatch.setattr("app.services.query.build_agent", lambda *args, **kwargs: Agent())
    response = client.post("/query", json={"text": "ethanol"}, headers=HEADERS)
    assert response.json()["abstained"] is True
    assert "Unsupported answer" not in response.json()["text_response"]


def test_greeting_avoids_model_calls(client, monkeypatch):
    def forbidden(*args):
        raise AssertionError("Greeting should not call a model")

    monkeypatch.setattr("app.services.query.build_agent", forbidden)
    assert client.post("/query", json={"text": "hi"}, headers=HEADERS).status_code == 200
