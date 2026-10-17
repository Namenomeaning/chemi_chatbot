"""Async LangChain chat adapter for OpenRouter's HTTP API."""

import json
import logging
from typing import Any

import httpx
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import SecretStr

from app.core.errors import ModelUnavailable

logger = logging.getLogger(__name__)


def serialize_message(message: BaseMessage) -> dict:
    roles = {"human": "user", "ai": "assistant", "system": "system", "tool": "tool"}
    if message.type not in roles:
        raise ValueError(f"Unsupported message type: {message.type}")
    result = {"role": roles[message.type], "content": message.content}
    if message.type == "tool":
        result["tool_call_id"] = message.tool_call_id
    if message.type == "ai" and message.tool_calls:
        result["tool_calls"] = [
            {
                "id": call["id"],
                "type": "function",
                "function": {
                    "name": call["name"],
                    "arguments": json.dumps(call["args"], ensure_ascii=False),
                },
            }
            for call in message.tool_calls
        ]
    return result


class OpenRouterChat(BaseChatModel):
    api_key: SecretStr
    base_url: str = "https://openrouter.ai/api/v1"
    model: str
    max_completion_tokens: int = 4000

    @property
    def _llm_type(self) -> str:
        return "openrouter-http"

    @property
    def _identifying_params(self) -> dict:
        return {"model": self.model}

    def bind_tools(self, tools, *, tool_choice=None, **kwargs):
        options = {"tools": [convert_to_openai_tool(tool) for tool in tools], **kwargs}
        if tool_choice is not None:
            options["tool_choice"] = tool_choice
        return self.bind(**options)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError("Use ainvoke: the Worker supports asynchronous model calls only.")

    async def _agenerate(self, messages, stop=None, run_manager=None, **kwargs: Any) -> ChatResult:
        payload = {
            "model": self.model,
            "messages": [serialize_message(message) for message in messages],
            "max_completion_tokens": self.max_completion_tokens,
            "reasoning": {"enabled": False},
        }
        for key in ("tools", "tool_choice", "parallel_tool_calls"):
            if key in kwargs:
                payload[key] = kwargs[key]
        if stop:
            payload["stop"] = stop
        try:
            async with httpx.AsyncClient(timeout=45) as client:
                response = await client.post(
                    f"{self.base_url.rstrip('/')}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self.api_key.get_secret_value()}",
                        "HTTP-Referer": "https://chemi.quangiz.me",
                        "X-Title": "CHEMI",
                    },
                    json=payload,
                )
            response.raise_for_status()
            body = response.json()
            choice = body["choices"][0]
            raw = choice["message"]
            tool_calls = []
            for call in raw.get("tool_calls") or []:
                arguments = json.loads(call["function"]["arguments"])
                if not isinstance(arguments, dict):
                    raise ValueError("Tool arguments must be a JSON object")
                tool_calls.append(
                    {"id": call["id"], "name": call["function"]["name"], "args": arguments, "type": "tool_call"}
                )
            usage = body.get("usage") or {}
            input_tokens = usage.get("prompt_tokens", 0) or 0
            output_tokens = usage.get("completion_tokens", 0) or 0
            message = AIMessage(
                content=raw.get("content") or "",
                tool_calls=tool_calls,
                response_metadata={
                    "model_name": body.get("model", self.model),
                    "finish_reason": choice.get("finish_reason"),
                },
                usage_metadata={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": usage.get("total_tokens") or input_tokens + output_tokens,
                },
            )
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            logger.warning("model_call_failed exception_type=%s", type(exc).__name__)
            raise ModelUnavailable() from exc
        return ChatResult(generations=[ChatGeneration(message=message)])
