"""CHEMI – máy chủ FastAPI cung cấp API cho chatbot Hóa học.

Cung cấp các điểm cuối để nhận truy vấn và trả kết quả (văn bản, hình ảnh,
âm thanh, câu hỏi luyện tập).
"""

import os
import base64
import asyncio
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from src.agent import invoke_agent, ChemistryResponse

load_dotenv()

# Thiết lập logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ============== Mẫu dữ liệu gửi lên/nhận về (Request/Response) ==============

class QueryRequest(BaseModel):
    """Mẫu dữ liệu yêu cầu mà giao diện gửi lên.

    Có thể gồm văn bản, hoặc kèm ảnh dưới dạng base64.
    """
    text: Optional[str] = Field(
        default=None,
        description="Nội dung văn bản người dùng nhập"
    )
    image_base64: Optional[str] = Field(
        default=None,
        description="Ảnh mã hóa base64 (PNG/JPEG), nếu có"
    )
    thread_id: Optional[str] = Field(
        default=None,
        description="Mã hội thoại để duy trì ngữ cảnh; tự tạo nếu bỏ trống"
    )


class QueryResponse(BaseModel):
    """Mẫu dữ liệu phản hồi cho giao diện hiển thị.

    Bao gồm văn bản, hình ảnh/âm thanh (nếu có) và dữ liệu quiz.
    """
    success: bool = Field(
        ...,
        description="Trạng thái xử lý (thành công/thất bại)"
    )
    thread_id: str = Field(
        ...,
        description="Mã hội thoại tương ứng với yêu cầu"
    )
    text_response: Optional[str] = Field(
        default=None,
        description="Câu trả lời bằng tiếng Việt"
    )
    image_base64: Optional[str] = Field(
        default=None,
        description="Hình ảnh trả về: base64 hoặc URL nếu là đường dẫn web"
    )
    audio_base64: Optional[str] = Field(
        default=None,
        description="Âm thanh trả về: base64 hoặc URL nếu là đường dẫn web"
    )
    quiz_data: Optional[dict] = Field(
        default=None,
        description="Dữ liệu câu hỏi luyện tập (nếu có)"
    )
    error: Optional[str] = Field(
        default=None,
        description="Thông báo lỗi (nếu có)"
    )


# ============== Hàm tiện ích ==============

def to_base64(file_path: Optional[str]) -> Optional[str]:
    """Chuyển tệp cục bộ sang base64; nếu đã là URL thì giữ nguyên."""
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
    """Xử lý truy vấn và tổng hợp phản hồi.

    Luồng xử lý: nhận văn bản/ảnh → gọi agent → chuyển đổi hình/âm thanh nếu cần → trả về.
    """
    if not text and not image_base64:
        raise HTTPException(400, "text or image required")

    thread_id = thread_id or f"thread-{os.urandom(8).hex()}"

    # Tạo nội dung thông điệp gửi cho agent
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
        # Chuyển quiz_data từ Pydantic model sang dict nếu có
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
        # Ghi log thông tin phản hồi
        img_len = len(response.image_base64) if response.image_base64 else 0
        audio_len = len(response.audio_base64) if response.audio_base64 else 0
        quiz_type = quiz_data.get("type") if quiz_data else None
        logger.info(f"Response: text={response.text_response[:80]}... | image={img_len} chars | audio={audio_len} chars | quiz={quiz_type}")
        return response
    except Exception as e:
        logger.error(f"Error creating response: {e}", exc_info=True)
        raise HTTPException(500, f"Response creation error: {str(e)}") from e


# ============== Ứng dụng FastAPI (khởi tạo API) ==============

app = FastAPI(title="CHEMI - Chemistry Chatbot API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

# Phục vụ tệp tĩnh (giao diện web demo)
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/health")
async def health():
    """Kiểm tra nhanh xem dịch vụ có đang chạy bình thường không."""
    return {"status": "ok", "service": "CHEMI Chemistry Chatbot"}


@app.get("/")
async def root():
    """Trả về giao diện chat (nếu có) hoặc thông tin dịch vụ."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"status": "ok", "service": "CHEMI Chemistry Chatbot", "ui": "Not found"}


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest):
    """Nhận câu hỏi (chữ/ảnh) từ giao diện và trả lời lại."""
    return await process_query(request.text, request.image_base64, request.thread_id)


# ============== Chạy trực tiếp (main) ==============

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
