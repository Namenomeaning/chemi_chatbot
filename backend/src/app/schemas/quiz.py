from typing import List, Optional

from pydantic import BaseModel, Field


class QuizData(BaseModel):
    """Cấu trúc dữ liệu thống nhất cho mọi dạng câu hỏi luyện tập.

    Dùng để hiển thị câu hỏi, phương án trả lời, chấm điểm và giải thích.
    """
    quiz_id: str = Field(description="Mã câu hỏi (để phân biệt các câu hỏi)")
    type: str = Field(description="Dạng bài: mcq, matching, free_text, listening")
    level: int = Field(description="Mức độ khó 1-4 (1 dễ – 4 khó)")
    topic: str = Field(description="Chủ đề của câu hỏi")

    # Nội dung câu hỏi
    question_text: str = Field(description="Nội dung câu hỏi")
    audio_script: Optional[str] = Field(default=None, description="Dùng cho dạng listening – nội dung cần phát âm")

    # Cách người dùng trả lời
    input_type: str = Field(description="Cách nhập: radio, select, text")
    options: Optional[List[str]] = Field(default=None, description="Phương án lựa chọn (nếu có)")
    match_items: Optional[List[dict]] = Field(default=None, description="Danh sách ghép cặp (cho dạng matching)")

    # Cách chấm điểm
    check_method: str = Field(description="Cách kiểm tra: exact (so khớp chính xác) hoặc fuzzy (linh hoạt)")
    correct_answer: str = Field(description="Đáp án đúng")
    accept_variants: Optional[List[str]] = Field(default=None, description="Các cách viết gần đúng (nếu chấp nhận)")

    # Phản hồi sau khi trả lời
    explanation: str = Field(description="Giải thích ngắn gọn, dễ hiểu")
