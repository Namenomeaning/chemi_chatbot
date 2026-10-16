import asyncio
import base64
import logging

import uuid

from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import check_rate_limit, get_env, get_settings
from app.schemas.query import QueryRequest, QueryResponse
from app.services.agent import build_agent, run_agent
from app.services.d1_saver import D1Saver
from app.tools.factory import AUDIO_ID, make_tools

logger = logging.getLogger(__name__)
router = APIRouter()


async def load_audio(env, audio_id: str | None) -> str | None:
    """Read audio from R2. The key must match the pattern the tool returns, never a model-chosen path."""
    if not audio_id or not AUDIO_ID.fullmatch(audio_id):
        return None
    obj = await env.ARTIFACTS.get(audio_id)
    if obj is None:
        return None
    return base64.b64encode(bytes(await obj.arrayBuffer())).decode()


@router.post("/query", response_model=QueryResponse, dependencies=[Depends(check_rate_limit)])
async def query(request: QueryRequest, env=Depends(get_env), settings=Depends(get_settings)):
    if not request.text and not request.image_base64:
        raise HTTPException(400, "text or image required")
    thread_id = request.thread_id or f"thread-{uuid.uuid4().hex[:16]}"

    if request.image_base64:
        content = [
            {"type": "text", "text": request.text or "Đây là hợp chất gì?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{request.image_base64}"}},
        ]
    else:
        content = request.text

    agent = build_agent(settings, D1Saver(env.DB), make_tools(settings, env.ARTIFACTS))
    try:
        result = await run_agent(agent, [{"role": "user", "content": content}], thread_id)
    except asyncio.TimeoutError:
        return QueryResponse(success=False, thread_id=thread_id, error="Timeout - vui lòng thử lại")
    except Exception as e:
        logger.error("Agent error: %s", e)
        if "recursion" in str(e).lower():
            return QueryResponse(success=False, thread_id=thread_id, error="Không tìm được thông tin")
        raise HTTPException(500, "Agent error") from e

    sr = result.get("structured_response")
    if sr is None:
        return QueryResponse(success=False, thread_id=thread_id, error="No response from agent")
    return QueryResponse(
        success=True,
        thread_id=thread_id,
        text_response=sr.text_response,
        image_base64=sr.image_url,
        audio_base64=await load_audio(env, sr.audio_url),
        quiz_data=sr.quiz_data.model_dump() if sr.quiz_data else None,
    )
