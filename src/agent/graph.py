"""Simplified LangGraph workflow using ReAct agent with tools."""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain.agents import create_agent
from langgraph.checkpoint.memory import MemorySaver
from langchain_openai import ChatOpenAI

from .tools import search_compound, generate_isomers
from ..core.logging import setup_logging

load_dotenv()
logger = setup_logging(__name__)


# Structured output schema
class ChemistryResponse(BaseModel):
    """Structured response from chemistry chatbot."""

    text_response: str = Field(
        description="Câu trả lời đầy đủ cho học sinh (markdown format)"
    )
    image_url: Optional[str] = Field(
        default=None,
        description="URL hình ảnh cấu trúc (lấy từ image_path trong kết quả search_compound)"
    )
    audio_url: Optional[str] = Field(
        default=None,
        description="URL audio phát âm (lấy từ audio_path trong kết quả search_compound)"
    )

# System prompt in Vietnamese for Grade 11 chemistry tutor
SYSTEM_PROMPT = """Bạn là CHEMI - gia sư Hóa học thân thiện, giúp học sinh lớp 11 Việt Nam học danh pháp IUPAC quốc tế.

## TOOLS:
- **search_compound(query)**: Tìm hợp chất → trả về image_path, audio_path
- **generate_isomers(smiles)**: Tạo đồng phân từ SMILES → trả về image_path

## QUY TẮC:
1. Khi học sinh hỏi về hợp chất/nguyên tố CỤ THỂ → GỌI search_compound() để lấy thông tin
2. Khi học sinh hỏi về ĐỒNG PHÂN → GỌI generate_isomers() với SMILES của chất đó
3. Sử dụng image_path và audio_path từ kết quả để trả về trong structured output
4. Với câu hỏi kiến thức CHUNG (so sánh, liệt kê, lý thuyết) → trả lời trực tiếp

## PHONG CÁCH TRẢ LỜI:
1. **Tên IUPAC**: Luôn dùng tên quốc tế + phiên âm tiếng Việt
   - Ví dụ: "Hydrogen (hai-đờ-rô-giần)", "Ethanol (ét-thờ-nol)"

2. **Sửa tên tiếng Việt nhẹ nhàng**:
   - "À, theo chuẩn IUPAC quốc tế thì mình gọi là **Sodium** nhé!"

3. **Gợi ý tiếp theo**: Cuối câu trả lời, gợi ý chủ đề liên quan
   - Ví dụ: "Bạn muốn tìm hiểu thêm về tính chất hóa học của chất này không?"

## OUTPUT FORMAT (BẮT BUỘC TUÂN THỦ):

### text_response:
- Chứa nội dung trả lời dạng markdown
- ❌ KHÔNG dùng `![text](url)` - UI tự hiển thị từ image_url
- ❌ KHÔNG dùng `[text]` đơn lẻ - gây lỗi hiển thị
- ✅ Chỉ dùng **bold**, *italic*, danh sách `-`

### image_url:
- Copy URL từ `image_path` của tool (search_compound hoặc generate_isomers)
- Nếu không có ảnh thì để null

### audio_url:
- Copy URL từ `audio_path` của search_compound
- Nếu không có audio thì để null
"""


# Global instances (lazy loaded)
_agent = None
_memory = None


def get_memory():
    """Get or create the memory checkpointer (singleton)."""
    global _memory
    if _memory is None:
        _memory = MemorySaver()
    return _memory


def build_agent():
    """Build the chemistry chatbot agent with tools and memory.

    Returns:
        Compiled ReAct agent with MemorySaver checkpointer
    """
    global _agent

    if _agent is not None:
        return _agent

    # Initialize LLM (OpenAI-compatible API)
    api_key = os.getenv("OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_BASE_URL", "https://gpt3.shupremium.com/v1")
    model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise ValueError("OPENAI_API_KEY not found in environment")

    llm = ChatOpenAI(
        model=model_name,
        api_key=api_key,
        base_url=base_url,
        temperature=0.3,
    )

    # Tools list
    tools = [search_compound, generate_isomers]

    # Create agent with shared memory and structured output (LangChain 1.0 API)
    _agent = create_agent(
        model=llm,
        tools=tools,
        checkpointer=get_memory(),
        system_prompt=SYSTEM_PROMPT,
        response_format=ChemistryResponse,
    )

    logger.info("Chemistry agent built with ReAct pattern and memory")
    return _agent


def get_agent():
    """Get the agent instance (lazy loading)."""
    return build_agent()
