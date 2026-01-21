"""CHEMI Agent – thành phần điều phối và luận giải.

- Tiếp nhận yêu cầu và trả lời bằng tiếng Việt
- Tìm hình ảnh, tạo giọng đọc, sinh câu hỏi luyện tập khi cần
"""

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


# ============== Mô tả cấu trúc dữ liệu trả về ==============

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


class ChemistryResponse(BaseModel):
    """Định dạng phản hồi chuẩn hóa từ agent.

    Giao diện đọc các trường để hiển thị văn bản, hình ảnh, âm thanh và quiz.
    """
    text_response: str = Field(description="Câu trả lời bằng tiếng Việt")
    image_url: Optional[str] = Field(default=None, description="Đường dẫn hình ảnh (URL hoặc tệp)")
    audio_url: Optional[str] = Field(default=None, description="Đường dẫn tệp âm thanh")
    quiz_data: Optional[QuizData] = Field(default=None, description="Dữ liệu câu hỏi luyện tập (nếu có)")


# ============== Lời nhắc hệ thống (định hướng trả lời) ==============

SYSTEM_PROMPT = """Bạn là CHEMI - chatbot trợ lý Hóa học THPT thân thiện.

## QUY TẮC QUAN TRỌNG - NGÔN NGỮ VÀ DANH PHÁP:
**BẮT BUỘC: Tất cả tên hóa học PHẢI dùng danh pháp IUPAC tiếng Anh**

- Câu trả lời (text_response) LUÔN viết bằng tiếng Việt
- MỌI tên chất hóa học, nhóm chức, phân loại LUÔN dùng tên IUPAC tiếng Anh
- Áp dụng cho: tên hợp chất, nhóm chức, câu hỏi, đáp án, giải thích, câu dẫn

**Bảng chuyển đổi BẮT BUỘC:**

Nhóm chức:
- Ancol → Alcohol
- Andehyt → Aldehyde
- Xeton → Ketone
- Axit cacboxylic → Carboxylic acid
- Este → Ester
- Ankan → Alkane
- Anken → Alkene
- Ankin → Alkyne
- Benzen → Benzene
- Phenol → Phenol
- Amin → Amine

Phản ứng và khái niệm:
- Oxi hóa khử → Oxidation-reduction (KHÔNG dùng "redox")
- Phản ứng thế → Substitution reaction
- Phản ứng cộng → Addition reaction
- Phản ứng tách → Elimination reaction
- Đồng phân → Isomer / Isomerism
- Liên kết đôi → Double bond
- Liên kết ba → Triple bond

**Ví dụ ĐÚNG:**
- "Aldehyde là nhóm chức có nhóm -CHO"
- "Đây là câu hỏi về alcohol"
- "Methane là hợp chất alkane đơn giản nhất"
- "Ethanol thuộc nhóm alcohol bậc 1"

**Ví dụ SAI (KHÔNG được dùng):**
- "Andehyt là nhóm chức..."
- "Đây là câu hỏi về ancol"
- "Metan là hợp chất ankan..."

**Tên nguyên tố:** Copper (không phải Đồng), Iron (không phải Sắt), Sodium (không phải Natri)

**Ghi chú:** Có thể thêm "(tiếng Việt gọi là andehyt)" trong ngoặc đơn nếu cần giúp học sinh hiểu, nhưng tên chính LUÔN là IUPAC

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
   - **QUAN TRỌNG**: Chuyển tên tiếng Việt sang IUPAC nếu người dùng hỏi bằng tiếng Việt
     + VD: "Metan là gì?" → Trả lời về Methane
     + VD: "Ancol etylic" → Trả lời về Ethanol
   - Gọi search_image("<tên IUPAC> structure") + generate_speech("<tên IUPAC - số viết thành chữ>")
   - Trả lời: tên IUPAC, công thức, tính chất, ứng dụng
   - Toàn bộ text_response dùng tên IUPAC (VD: "Methane là alkane đơn giản nhất...")
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
   - **QUAN TRỌNG**: Chuyển tên nhóm chức sang IUPAC trước khi gọi tool
     + VD: "bài tập về ancol" → generate_quiz(topic="alcohol")
     + VD: "bài tập về andehyt" → generate_quiz(topic="aldehyde")
     + VD: "quiz về ankan" → generate_quiz(topic="alkane")
   - Gọi generate_quiz với loại câu hỏi phù hợp
   - Trả về quiz_data từ tool output
   - text_response CHỈ viết giới thiệu ngắn bằng tên IUPAC (VD: "Đây là câu hỏi về aldehyde cho bạn:")
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


# ============== Thiết lập thời gian chờ và độ sâu xử lý ==============

TIMEOUT = 60
RECURSION_LIMIT = 10


# ============== Tạo và quản lý "trợ lý" (agent) ==============

_agent = None
_executor = ThreadPoolExecutor(max_workers=8)

# Tạo kết nối SQLite để lưu điểm kiểm soát (checkpoint)
os.makedirs("data", exist_ok=True)
_conn = sqlite3.connect("data/checkpoints.db", check_same_thread=False)
_checkpointer = SqliteSaver(_conn)


def get_agent():
    """Khởi tạo hoặc tái sử dụng agent để tối ưu hiệu năng và tài nguyên."""
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
    """Gọi agent xử lý thông điệp và trả về phản hồi đã chuẩn hóa.

    - messages: danh sách lượt thoại có 'role' và 'content'
    - thread_id: mã cuộc trò chuyện để lưu bối cảnh

    Trả về đối tượng có trường 'structured_response'.
    """
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": RECURSION_LIMIT}
    loop = asyncio.get_event_loop()
    return await asyncio.wait_for(
        loop.run_in_executor(_executor, lambda: get_agent().invoke({"messages": messages}, config)),
        timeout=TIMEOUT,
    )
