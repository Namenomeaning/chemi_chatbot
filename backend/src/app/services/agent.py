import asyncio
import ssl

# Import at startup so the Worker snapshot holds it (a lazy import cost about 1 s of CPU on the first request).
# langchain_openai builds an SSL context at import, which fails in the startup phase. The context is only
# used with a proxy, so stub it for the import.
_create_default_context = ssl.create_default_context
ssl.create_default_context = lambda *args, **kwargs: None
try:
    from langchain_openai import ChatOpenAI

    ChatOpenAI(api_key="warmup", model="warmup")  # the first instance costs about 0.4 s of CPU
finally:
    ssl.create_default_context = _create_default_context

from langgraph.prebuilt import create_react_agent

from app.core.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.schemas.query import ChemistryResponse

TIMEOUT = 60
RECURSION_LIMIT = 10


def build_agent(settings: Settings, checkpointer, tools):
    llm = ChatOpenAI(
        api_key=settings.openrouter_api_key,
        base_url=settings.openrouter_base_url,
        model=settings.llm_model,
        default_headers={"HTTP-Referer": "https://chemi.quangiz.me", "X-Title": "CHEMI"},
        max_completion_tokens=4000,
        # openai/gpt-6-luna does not support temperature. It reasons before it answers (about 170 hidden
        # tokens, 2 s per call, measured). Turn that off.
        extra_body={"reasoning": {"enabled": False}},
    )
    return create_react_agent(
        llm, tools, prompt=SYSTEM_PROMPT, response_format=ChemistryResponse, checkpointer=checkpointer
    )


async def run_agent(agent, messages: list, thread_id: str, *, max_seconds: int = TIMEOUT) -> dict:
    """Run the agent. A timeout cancels the run, so no background work keeps going."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    return await asyncio.wait_for(agent.ainvoke({"messages": messages}, config), timeout=max_seconds)
