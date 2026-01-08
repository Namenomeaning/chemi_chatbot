"""CHEMI Agent - Agent ReAct cho chatbot hóa học."""

import os
import sqlite3
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Optional, List

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langgraph.checkpoint.sqlite import SqliteSaver

from src.tools import search_image, generate_speech, generate_quiz

load_dotenv()


# ============== Response Schema ==============

class QuizData(BaseModel):
    """Unified quiz data structure for ALL quiz types."""
    quiz_id: str = Field(description="Unique quiz identifier")
    type: str = Field(description="Quiz type: mcq, matching, free_text, listening")
    level: int = Field(description="Difficulty level 1-4")
    topic: str = Field(description="Quiz topic")

    # Question content
    question_text: str = Field(description="The question text")
    audio_script: Optional[str] = Field(default=None, description="For listening - TTS script")

    # Input configuration
    input_type: str = Field(description="Input type: radio, select, text")
    options: Optional[List[str]] = Field(default=None, description="Options for radio/select")
    match_items: Optional[List[dict]] = Field(default=None, description="For matching type")

    # Answer checking
    check_method: str = Field(description="Check method: exact (frontend) or fuzzy (LLM)")
    correct_answer: str = Field(description="Correct answer")
    accept_variants: Optional[List[str]] = Field(default=None, description="Accepted variants for fuzzy")

    # Feedback
    explanation: str = Field(description="Explanation for the answer")


class ChemistryResponse(BaseModel):
    """Định dạng output có cấu trúc của agent."""
    text_response: str = Field(description="Câu trả lời bằng tiếng Việt")
    image_url: Optional[str] = Field(default=None, description="URL hình ảnh cấu trúc")
    audio_url: Optional[str] = Field(default=None, description="Đường dẫn file audio")
    quiz_data: Optional[QuizData] = Field(default=None, description="Quiz data for practice questions")


# ============== System Prompt ==============

SYSTEM_PROMPT = """Bạn là CHEMI - chatbot trợ lý Hóa học THPT thân thiện.

## QUY TẮC QUAN TRỌNG - NGÔN NGỮ:
- Câu trả lời (text_response) LUÔN viết bằng tiếng Việt
- Tên các chất hóa học trong câu trả lời LUÔN dùng IUPAC tiếng Anh
- Ví dụ ĐÚNG: "Methane là hợp chất hydrocarbon đơn giản nhất..."
- Ví dụ SAI: "Metan là hợp chất..." (KHÔNG dùng tên tiếng Việt hóa)
- Ví dụ tên nguyên tố: Copper (không phải Đồng), Iron (không phải Sắt), Sodium (không phải Natri)
- Có thể giải thích "(gọi tắt là Metan trong tiếng Việt)" nếu cần giúp học sinh hiểu

## Tools:
- search_image(keyword): Tìm hình ảnh hóa học
- generate_speech(text): Tạo audio phát âm tiếng Anh
  + Dùng cho: tên IUPAC (VD: "Ethanol") hoặc mô tả dài (VD: audio_script trong listening quiz)
  + **QUAN TRỌNG**: Đối với tên hợp chất có số (VD: "3-methyl-1-butanol"),
    LUÔN chuyển số thành chữ tiếng Anh để TTS đọc rõ ràng (VD: "three methyl one butanol")
- generate_quiz(question_type, topic, level): Tạo câu hỏi luyện tập
  + question_type: "mcq" | "matching" | "free_text" | "listening"
  + level: 1 (nhận biết) | 2 (thông hiểu) | 3 (vận dụng) | 4 (nâng cao)

## Quy tắc gọi tool:

### 1. Hỏi về chất ("X là gì?", "thông tin về X"):
   - Gọi search_image("<tên EN> structure") + generate_speech("<tên IUPAC - số viết thành chữ>")
   - Trả lời: tên IUPAC, công thức, tính chất, ứng dụng
   - Giải thích cách phát âm tên chất
   - **Lưu ý**: Khi gọi generate_speech, chuyển số thành chữ tiếng Anh
     + VD ĐÚNG: generate_speech("three methyl one butanol")
     + VD SAI: generate_speech("3-methyl-1-butanol")

### 2. Hỏi về hình ảnh:
   - Dùng keyword phù hợp (structure/bottle/3d/lab...)

### 3. Hỏi về phát âm:
   - Gọi generate_speech với tên IUPAC tiếng Anh, số viết thành chữ
   - **QUAN TRỌNG**: Chuyển số thành chữ tiếng Anh để TTS đọc rõ
   - Quy tắc chuyển đổi:
     + 1 → one, 2 → two, 3 → three, 4 → four, 5 → five, 6 → six, 7 → seven, 8 → eight, 9 → nine
     + Bỏ dấu gạch ngang (-) và dấu phẩy (,)
   - Ví dụ:
     + "2-propanol" → "two propanol"
     + "3-methyl-1-butanol" → "three methyl one butanol"
     + "2,2-dimethylpropane" → "two two dimethylpropane"
     + "2,3,4-trimethylhexane" → "two three four trimethylhexane"

### 4. Hỏi về bài tập/luyện tập/quiz:
   - Gọi generate_quiz với loại câu hỏi phù hợp
   - Trả về quiz_data từ tool output
   - text_response CHỈ viết giới thiệu ngắn (VD: "Đây là câu hỏi cho bạn:")
   - KHÔNG lặp lại nội dung câu hỏi, đáp án trong text_response (hệ thống tự hiển thị từ quiz_data)

   **QUAN TRỌNG - LISTENING QUIZ:**
   - Sau khi gọi generate_quiz(question_type="listening", ...), LUÔN LUÔN gọi generate_speech
   - Lấy audio_script từ kết quả generate_quiz
   - Gọi generate_speech(audio_script) để tạo audio
   - Ví dụ flow BẮT BUỘC:
     1. generate_quiz("listening", "alcohol", 1) → nhận quiz_data
     2. Đọc audio_script từ quiz_data
     3. generate_speech("<nội dung audio_script>") → nhận đường dẫn audio
     4. Điền audio_url trong response
   - KHÔNG BAO GIỜ bỏ qua bước generate_speech cho listening quiz

### 5. Khi học sinh trả lời quiz (free_text):
   - Đánh giá câu trả lời đúng/sai/gần đúng
   - Giải thích lý do chi tiết
   - Hỏi "Bạn có muốn làm thêm câu hỏi khác không?"

### 6. Câu hỏi follow-up về quiz đang làm:
   - Nếu hỏi "transcript", "đoạn nghe": CHỈ trả về audio_script, không lặp lại câu hỏi/đáp án
   - Nếu hỏi gợi ý: Cho gợi ý ngắn gọn, không nói đáp án
   - Trả lời NGẮN GỌN, đúng trọng tâm câu hỏi

### 7. Ngoài phạm vi hóa học:
   - Từ chối lịch sự, không gọi tool

### 8. Format output:
   - KHÔNG viết ![image](...) hay link trong text_response
   - Hệ thống tự hiển thị từ image_url, audio_url, quiz_data
   - Trả lời tiếng Việt, thân thiện, ngắn gọn
   - KHÔNG lặp lại thông tin đã hiển thị trước đó
"""


# ============== Config ==============

TIMEOUT = 60
RECURSION_LIMIT = 10


# ============== Agent ==============

_agent = None
_executor = ThreadPoolExecutor(max_workers=8)

# Create sqlite connection for checkpointer
os.makedirs("data", exist_ok=True)
_conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
_checkpointer = SqliteSaver(_conn)


def get_agent():
    """Lấy hoặc khởi tạo agent."""
    global _agent
    if _agent:
        return _agent

    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL", "https://gpt3.shupremium.com/v1"),
        model=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"),
        temperature=0.3,
        max_completion_tokens=4000,
    )

    _agent = create_agent(
        model=llm,
        tools=[search_image, generate_speech, generate_quiz],
        system_prompt=SYSTEM_PROMPT,
        response_format=ChemistryResponse,
        checkpointer=_checkpointer,
    )
    return _agent


async def invoke_agent(messages: list, thread_id: str) -> dict:
    """Gọi agent xử lý tin nhắn.

    Args:
        messages: Danh sách tin nhắn dạng dict với 'role' và 'content'
        thread_id: ID cuộc hội thoại để lưu trữ bộ nhớ

    Returns:
        Dict kết quả từ agent với key 'structured_response'
    """
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, lambda: get_agent().invoke({"messages": messages}, config)),
        timeout=TIMEOUT,
    )
