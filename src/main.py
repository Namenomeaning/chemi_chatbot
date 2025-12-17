"""FastAPI backend for chemistry chatbot (simplified with ReAct agent)."""

import os
import json
import sys
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Add project root to path for direct script execution
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import base64
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, Tuple

from fastapi import FastAPI, HTTPException, UploadFile, File, Form

# Agent timeout and recursion settings
AGENT_TIMEOUT = 10  # seconds
AGENT_RECURSION_LIMIT = 5  # max tool calls (prevents infinite loops)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from src.core.logging import setup_logging
from src.agent import get_agent

load_dotenv(override=True)
logger = setup_logging(__name__)

# Thread pool for running blocking agent calls
_executor = ThreadPoolExecutor(max_workers=4)


async def invoke_agent_with_timeout(messages, config, timeout=AGENT_TIMEOUT):
    """Invoke agent with timeout to prevent infinite loops.

    Args:
        messages: Input messages for the agent
        config: Agent config (thread_id, recursion_limit)
        timeout: Max seconds to wait for response

    Returns:
        Agent result dict

    Raises:
        asyncio.TimeoutError: If agent takes too long
    """
    loop = asyncio.get_event_loop()

    def _invoke():
        return get_agent().invoke({"messages": messages}, config)

    return await asyncio.wait_for(
        loop.run_in_executor(_executor, _invoke),
        timeout=timeout
    )


def parse_structured_response(content: str) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse structured JSON response from agent.

    The agent returns JSON with: text_response, image_url, audio_url

    Args:
        content: JSON string or plain text from agent

    Returns:
        Tuple of (text_response, image_url, audio_url)
    """
    import re

    try:
        # Try to parse as JSON (structured output)
        data = json.loads(content)
        text_response = data.get("text_response", content)
        image_url = data.get("image_url")
        audio_url = data.get("audio_url")

        # Strip markdown images from text_response to avoid duplicates
        # Pattern: ![any text](any url)
        text_response = re.sub(r'!\[[^\]]*\]\([^)]+\)\n*', '', text_response).strip()

        return text_response, image_url, audio_url
    except (json.JSONDecodeError, TypeError):
        # Fallback: treat as plain text (no media)
        logger.debug("Response is not JSON, treating as plain text")
        return content, None, None


def file_or_url_to_base64(file_path: Optional[str]) -> Optional[str]:
    """Convert file to base64 or return URL directly.

    Args:
        file_path: Path to file (local or URL)

    Returns:
        Base64-encoded string for local files, or URL string for remote URLs
    """
    if not file_path:
        return None

    # If it's a URL, return it directly
    if file_path.startswith(("http://", "https://", "data:")):
        return file_path

    try:
        base_dir = Path(__file__).parent.parent
        full_path = Path(file_path)

        if not full_path.is_absolute():
            full_path = base_dir / file_path

        if not full_path.exists():
            full_path = base_dir / "data" / file_path

        if not full_path.exists():
            logger.warning(f"File not found: {file_path}")
            return None

        with open(full_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    except Exception as e:
        logger.error(f"Error encoding file {file_path}: {str(e)}")
        return None


# Pydantic Schemas
class QueryRequest(BaseModel):
    """Request schema for chemistry query."""
    text: Optional[str] = Field(default=None, description="Text query")
    image_base64: Optional[str] = Field(default=None, description="Base64-encoded image")
    thread_id: Optional[str] = Field(default=None, description="Thread ID for conversation context")


class QueryResponse(BaseModel):
    """Response schema for chemistry query."""
    success: bool
    thread_id: str
    text_response: Optional[str] = None
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    logger.info("FastAPI startup: Chemistry chatbot with ReAct agent ready")
    yield
    logger.info("FastAPI shutdown: Cleaning up...")


# FastAPI app
app = FastAPI(
    title="Chemistry Chatbot API",
    description="ReAct agent-powered chemistry chatbot for high school students",
    version="2.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "ok", "version": "2.0.0", "agent": "ReAct"}


@app.post("/query", response_model=QueryResponse)
async def query_chemistry(request: QueryRequest):
    """Main query endpoint using ReAct agent.

    Args:
        request: QueryRequest with text, image_base64, thread_id

    Returns:
        QueryResponse with text_response, image, audio
    """
    try:
        if not request.text and not request.image_base64:
            raise HTTPException(status_code=400, detail="Either text or image_base64 required")

        thread_id = request.thread_id or f"thread-{os.urandom(8).hex()}"

        logger.info(f"Query received - thread_id: {thread_id}, text: {request.text[:50] if request.text else 'None'}...")

        # Build message content
        content = []
        if request.text:
            content.append({"type": "text", "text": request.text})

        if request.image_base64:
            try:
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{request.image_base64}"}
                })
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64: {str(e)}")

        # Invoke agent with timeout and recursion limit
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": AGENT_RECURSION_LIMIT
        }
        try:
            result = await invoke_agent_with_timeout(
                [HumanMessage(content=content if len(content) > 1 else request.text)],
                config
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent timeout after {AGENT_TIMEOUT}s - thread_id: {thread_id}")
            # Return new thread_id to avoid corrupted conversation state
            return QueryResponse(
                success=False,
                thread_id=f"thread-{os.urandom(8).hex()}",
                error="Xin lỗi, yêu cầu mất quá nhiều thời gian. Vui lòng thử lại với câu hỏi đơn giản hơn."
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "recursion" in error_msg or "tool_call" in error_msg or "429" in str(e):
                logger.warning(f"Agent error (recursion/tool_call) - thread_id: {thread_id}, error: {e}")
                # Return new thread_id to avoid corrupted conversation state
                return QueryResponse(
                    success=False,
                    thread_id=f"thread-{os.urandom(8).hex()}",
                    error="Xin lỗi, mình không tìm được thông tin phù hợp. Thử hỏi về chất khác nhé!"
                )
            raise

        # Extract response text from last AI message
        messages = result.get("messages", [])
        if not messages:
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error="No response generated"
            )

        # Get last AI message
        last_message = messages[-1]
        response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # Parse structured JSON response
        text_response, image_url, audio_url = parse_structured_response(response_content)

        # Convert to base64 if local files
        image_base64 = file_or_url_to_base64(image_url)
        audio_base64 = file_or_url_to_base64(audio_url)

        logger.info(f"Query succeeded - thread_id: {thread_id}, has_image: {bool(image_url)}, has_audio: {bool(audio_url)}")

        return QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response=text_response,
            image_base64=image_base64,
            audio_base64=audio_base64,
            metadata={"message_count": len(messages)}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query exception - error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/upload", response_model=QueryResponse)
async def query_with_upload(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None)
):
    """Query endpoint with file upload.

    Args:
        text: Text query
        image: Image file
        thread_id: Thread ID

    Returns:
        QueryResponse
    """
    try:
        has_text = text and text.strip()
        has_image = image is not None

        if not has_text and not has_image:
            raise HTTPException(status_code=400, detail="Either text or image required")

        thread_id = thread_id or f"thread-{os.urandom(8).hex()}"

        # Build message content
        content = []
        if has_text:
            content.append({"type": "text", "text": text})

        if has_image:
            image_bytes = await image.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"}
            })

        # Invoke agent with timeout and recursion limit
        config = {
            "configurable": {"thread_id": thread_id},
            "recursion_limit": AGENT_RECURSION_LIMIT
        }
        try:
            result = await invoke_agent_with_timeout(
                [HumanMessage(content=content if len(content) > 1 else text)],
                config
            )
        except asyncio.TimeoutError:
            logger.warning(f"Agent timeout after {AGENT_TIMEOUT}s - thread_id: {thread_id}")
            return QueryResponse(
                success=False,
                thread_id=f"thread-{os.urandom(8).hex()}",
                error="Xin lỗi, yêu cầu mất quá nhiều thời gian. Vui lòng thử lại với câu hỏi đơn giản hơn."
            )
        except Exception as e:
            error_msg = str(e).lower()
            if "recursion" in error_msg or "tool_call" in error_msg or "429" in str(e):
                logger.warning(f"Agent error (recursion/tool_call) - thread_id: {thread_id}, error: {e}")
                return QueryResponse(
                    success=False,
                    thread_id=f"thread-{os.urandom(8).hex()}",
                    error="Xin lỗi, mình không tìm được thông tin phù hợp. Thử hỏi về chất khác nhé!"
                )
            raise

        # Extract response
        messages = result.get("messages", [])
        if not messages:
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error="No response generated"
            )

        last_message = messages[-1]
        response_content = last_message.content if hasattr(last_message, 'content') else str(last_message)

        # Parse structured JSON response
        text_response, image_url, audio_url = parse_structured_response(response_content)
        image_base64 = file_or_url_to_base64(image_url)
        audio_base64 = file_or_url_to_base64(audio_url)

        logger.info(f"Query succeeded - thread_id: {thread_id}")

        return QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response=text_response,
            image_base64=image_base64,
            audio_base64=audio_base64,
            metadata={"message_count": len(messages)}
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query exception - error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve static files (images, audio).

    Args:
        file_path: Relative path

    Returns:
        FileResponse
    """
    try:
        base_dir = Path(__file__).parent.parent
        full_path = base_dir / "data" / file_path

        if not full_path.resolve().is_relative_to(base_dir.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        return FileResponse(path=str(full_path))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
