import asyncio

import pytest

from app.core.errors import AgentTimeout
from app.services.agent import run_agent


class SlowAgent:
    async def ainvoke(self, messages, config):
        await asyncio.sleep(10)


@pytest.mark.asyncio
async def test_run_agent_raises_agent_timeout():
    with pytest.raises(AgentTimeout):
        await run_agent(
            SlowAgent(),
            [{"role": "user", "content": "Hello"}],
            "test-thread",
            max_seconds=0.01,
        )
