import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from app.services.agent import read_turn
from app.services.audio import load_audio
from app.services.quiz import parse_quiz
from tests.fakes import FakeR2


@pytest.mark.asyncio
async def test_audio_round_trip_and_key_validation():
    bucket = FakeR2()
    key = "audio/" + "a" * 32
    await bucket.put(key, b"audio-bytes")
    assert await load_audio(bucket, key) == "YXVkaW8tYnl0ZXM="
    assert await load_audio(bucket, "../../secret") is None
    assert bucket.reads == [key]
    assert await load_audio(None, key) is None


def test_only_current_turn_artifacts_are_returned():
    messages = [
        HumanMessage(content="old"),
        ToolMessage(content="old", tool_call_id="1", artifact={"kind": "audio", "key": "old"}),
        AIMessage(content="old answer"),
        HumanMessage(content="new"),
        ToolMessage(content="new", tool_call_id="2", artifact={"kind": "image", "url": "https://example.com/image"}),
        AIMessage(content="new answer"),
    ]
    text, artifacts = read_turn(messages)
    assert text == "new answer"
    assert set(artifacts) == {"image"}


def test_malformed_quiz_is_dropped():
    assert parse_quiz({"question_text": "incomplete"}) is None
