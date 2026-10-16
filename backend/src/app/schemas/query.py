from typing import Optional

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    text: Optional[str] = Field(default=None, description="Nội dung văn bản người dùng nhập")
    image_base64: Optional[str] = Field(default=None, description="Ảnh mã hóa base64 (PNG/JPEG), nếu có")
    thread_id: Optional[str] = Field(default=None, description="Mã hội thoại; tự tạo nếu bỏ trống")


class QueryResponse(BaseModel):
    success: bool
    thread_id: str
    text_response: Optional[str] = None
    image_base64: Optional[str] = Field(default=None, description="Base64 hoặc URL của hình ảnh")
    audio_base64: Optional[str] = None
    quiz_data: Optional[dict] = None
    error: Optional[str] = None

