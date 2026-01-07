"""CHEMI - Backend FastAPI cho Chatbot Hóa học."""

import os
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.agent import invoke_agent, ChemistryResponse

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Request/Response Schemas ==============

class QueryRequest(BaseModel):
    """Request API cho truy vấn văn bản/hình ảnh."""
    text: Optional[str] = None
    image_base64: Optional[str] = None
    thread_id: Optional[str] = None


class QueryResponse(BaseModel):
    """Response API trả về cho client."""
    success: bool
    thread_id: str
    text_response: Optional[str] = None
    image_base64: Optional[str] = None
    audio_base64: Optional[str] = None
    quiz_data: Optional[dict] = None
    error: Optional[str] = None


# ============== Helpers ==============

def to_base64(file_path: Optional[str]) -> Optional[str]:
    """Chuyển đổi file cục bộ sang base64 hoặc trả về URL trực tiếp."""
    if not file_path:
        return None
    if file_path.startswith(("http://", "https://")):
        return file_path
    path = Path(file_path)
    return base64.b64encode(path.read_bytes()).decode() if path.exists() else None


async def process_query(
    text: Optional[str],
    image_base64: Optional[str],
    thread_id: Optional[str]
) -> QueryResponse:
    """Xử lý truy vấn và trả về kết quả."""
    if not text and not image_base64:
        raise HTTPException(400, "text or image required")

    thread_id = thread_id or f"thread-{os.urandom(8).hex()}"

    # Build message content
    if image_base64:
        content = [
            {"type": "text", "text": text or "Đây là hợp chất gì?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_base64}"}},
        ]
    else:
        content = text

    try:
        result = await invoke_agent([{"role": "user", "content": content}], thread_id)
    except asyncio.TimeoutError:
        return QueryResponse(success=False, thread_id=thread_id, error="Timeout - vui lòng thử lại")
    except Exception as e:
        if "recursion" in str(e).lower():
            return QueryResponse(success=False, thread_id=thread_id, error="Không tìm được thông tin")
        raise HTTPException(500, str(e)) from e

    if not (sr := result.get("structured_response")):
        return QueryResponse(success=False, thread_id=thread_id, error="No response from agent")

    try:
        # Convert quiz_data from Pydantic model to dict if present
        quiz_data = None
        if sr.quiz_data:
            logger.info(f"Converting quiz_data: {type(sr.quiz_data)}")
            quiz_data = sr.quiz_data.model_dump() if hasattr(sr.quiz_data, 'model_dump') else sr.quiz_data

        logger.info(f"Converting image_url: {sr.image_url}")
        image_b64 = to_base64(sr.image_url)

        logger.info(f"Converting audio_url: {sr.audio_url}")
        audio_b64 = to_base64(sr.audio_url)

        response = QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response=sr.text_response,
            image_base64=image_b64,
            audio_base64=audio_b64,
            quiz_data=quiz_data,
        )
        # Log response
        img_len = len(response.image_base64) if response.image_base64 else 0
        audio_len = len(response.audio_base64) if response.audio_base64 else 0
        quiz_type = quiz_data.get("type") if quiz_data else None
        logger.info(f"Response: text={response.text_response[:80]}... | image={img_len} chars | audio={audio_len} chars | quiz={quiz_type}")
        return response
    except Exception as e:
        logger.error(f"Error creating response: {e}", exc_info=True)
        raise HTTPException(500, f"Response creation error: {str(e)}") from e


# ============== FastAPI App ==============

app = FastAPI(title="CHEMI - Chemistry Chatbot API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    """Endpoint kiểm tra trạng thái hoạt động."""
    return {"status": "ok", "service": "CHEMI Chemistry Chatbot"}


@app.get("/")
async def root():
    """Phục vụ giao diện chat chính."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"status": "ok", "service": "CHEMI Chemistry Chatbot", "ui": "Not found"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Endpoint truy vấn cho văn bản hoặc hình ảnh base64."""
    return await process_query(request.text, request.image_base64, request.thread_id)


# ============== Main ==============

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8000")),
        reload=os.getenv("ENV", "production") != "production",
        workers=1,
        limit_concurrency=50,
    )
