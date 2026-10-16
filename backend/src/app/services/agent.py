import asyncio

from langgraph.prebuilt import create_react_agent

from app.core.config import Settings
from app.prompts import SYSTEM_PROMPT
from app.schemas.query import ChemistryResponse

TIMEOUT = 60
RECURSION_LIMIT = 10


def build_agent(settings: Settings, checkpointer, tools):
    # Import here: langchain_openai builds an SSL context on import, which fails while the Worker starts.
    from langchain_openai import ChatOpenAI

    llm = ChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
        model=settings.openai_model,
        temperature=0.3,
        max_completion_tokens=4000,
    )
    return create_react_agent(
        llm, tools, prompt=SYSTEM_PROMPT, response_format=ChemistryResponse, checkpointer=checkpointer
    )


async def run_agent(agent, messages: list, thread_id: str, *, max_seconds: int = TIMEOUT) -> dict:
    """Run the agent. A timeout cancels the run, so no background work keeps going."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    return await asyncio.wait_for(agent.ainvoke({"messages": messages}, config), timeout=max_seconds)
