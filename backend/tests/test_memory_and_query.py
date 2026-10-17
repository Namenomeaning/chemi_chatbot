import pytest
from langchain_core.messages import AIMessage
from langgraph.graph import END, START, MessagesState, StateGraph

from app.services.d1_saver import D1Saver
from tests.fakes import FakeD1

HEADERS = {"X-API-Key": "test-access-key"}


def fake_graph(checkpointer):
    async def respond(state):
        users = [str(m.content) for m in state["messages"] if m.type == "human"]
        return {"messages": [AIMessage(content=" | ".join(users))]}

    graph = StateGraph(MessagesState)
    graph.add_node("respond", respond)
    graph.add_edge(START, "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


@pytest.mark.asyncio
async def test_memory_survives_new_database_connection(tmp_path):
    path = tmp_path / "memory.sqlite"
    first_db = FakeD1(path)
    first = fake_graph(D1Saver(first_db))
    config = {"configurable": {"thread_id": "owner:conversation"}}
    await first.ainvoke({"messages": [{"role": "user", "content": "remember ethanol"}]}, config)
    first_db.connection.close()
    second_db = FakeD1(path)
    second = fake_graph(D1Saver(second_db))
    result = await second.ainvoke({"messages": [{"role": "user", "content": "its formula?"}]}, config)
    assert "remember ethanol" in result["messages"][-1].content
    isolated = await second.ainvoke(
        {"messages": [{"role": "user", "content": "separate"}]}, {"configurable": {"thread_id": "other:conversation"}}
    )
    assert isolated["messages"][-1].content == "separate"
    second_db.connection.close()


def test_query_uses_memory_and_isolates_api_keys(client, monkeypatch, env):
    monkeypatch.setattr("app.services.query.build_agent", lambda settings, saver, tools: fake_graph(saver))
    first = client.post("/query", json={"text": "ethanol"}, headers=HEADERS)
    assert first.status_code == 200
    thread = first.json()["thread_id"]
    second = client.post("/query", json={"text": "formula?", "thread_id": thread}, headers=HEADERS)
    assert second.json()["text_response"] == "ethanol | formula?"
    env.API_KEYS = "test-access-key,second-key"
    other = client.post(
        "/query", json={"text": "independent question", "thread_id": thread}, headers={"X-API-Key": "second-key"}
    )
    assert other.json()["text_response"] == "independent question"
