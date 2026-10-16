from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.quiz import QuizData


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


class ChemistryResponse(BaseModel):
    """Định dạng phản hồi chuẩn hóa từ agent."""

    text_response: str = Field(description="Câu trả lời bằng tiếng Việt")
    image_url: Optional[str] = Field(default=None, description="URL hình ảnh")
    audio_url: Optional[str] = Field(default=None, description="Mã âm thanh do generate_speech trả về (dạng audio/<id>)")
    quiz_data: Optional[QuizData] = Field(default=None, description="Dữ liệu câu hỏi luyện tập (nếu có)")
