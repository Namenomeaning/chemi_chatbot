import asyncio

from langgraph.errors import GraphRecursionError
from langgraph.prebuilt import create_react_agent

from app.core.config import Settings
from app.core.errors import AgentLimitReached, AgentTimeout
from app.prompts import SYSTEM_PROMPT

TIMEOUT = 60
RECURSION_LIMIT = 10


def build_agent(settings: Settings, checkpointer, tools, *, context: str = ""):
    from app.services.chat_model import OpenRouterChat

    llm = OpenRouterChat(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=settings.llm_model,
    )
    return create_react_agent(
        llm, tools, prompt=SYSTEM_PROMPT + ("\n\n" + context if context else ""), checkpointer=checkpointer
    )


async def run_agent(agent, messages: list, thread_id: str, *, max_seconds: float = TIMEOUT) -> dict:
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    try:
        return await asyncio.wait_for(agent.ainvoke({"messages": messages}, config), timeout=max_seconds)
    except asyncio.TimeoutError as exc:
        raise AgentTimeout() from exc
    except GraphRecursionError as exc:
        raise AgentLimitReached() from exc


def read_turn(messages: list) -> tuple[str, dict]:
    """Return the final answer text and the artifacts that tools produced in the latest turn.

    Artifacts are keyed by kind. If a tool ran twice, the last result wins.
    """
    start = max((i for i, m in enumerate(messages) if m.type == "human"), default=-1) + 1
    turn = messages[start:]
    artifacts = {a["kind"]: a for m in turn if m.type == "tool" and (a := m.artifact)}
    text = ""
    if turn and turn[-1].type == "ai":
        content = turn[-1].content
        text = (
            content if isinstance(content, str) else "".join(b.get("text", "") for b in content if isinstance(b, dict))
        )
    return text.strip(), artifacts
