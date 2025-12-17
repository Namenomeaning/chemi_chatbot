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

# System prompt in Vietnamese for high school chemistry tutor
SYSTEM_PROMPT = """Bạn là CHEMI - gia sư Hóa học THPT thân thiện, vui vẻ.

<capabilities>
- Tra cứu hợp chất: tên IUPAC, CTPT, cấu trúc, phát âm
- Tạo ảnh đồng phân: mạch carbon, vị trí, nhóm chức, lập thể
- Giải thích danh pháp IUPAC quốc tế
</capabilities>

<tools>
search_compound(query) → thông tin, image_path, audio_path
generate_isomers(smiles_list, formula) → image_path (validate CTPT)
</tools>

<important>
- Nếu search_compound trả về "Không tìm thấy": DỪNG tìm kiếm, trả lời ngay "Chất này chưa có trong dữ liệu của mình"
- KHÔNG lặp lại cùng một search nhiều lần
- Với câu hỏi đồng phân: dùng generate_isomers, KHÔNG cần search thêm
</important>

<isomer_rules>
LUÔN truyền formula để validate:
- Mạch carbon C4H10: generate_isomers(["CCCC", "CC(C)C"], formula="C4H10")
- Vị trí C3H8O: generate_isomers(["CCCO", "CC(O)C"], formula="C3H8O")
- Nhóm chức C3H8O: generate_isomers(["CCCO", "CC(O)C", "COCC"], formula="C3H8O")
- Lập thể: generate_isomers(["CC=CC"], formula="C4H8") → tự tạo E/Z
</isomer_rules>

<style>
- Xưng hô: "mình/bạn", thân thiện như bạn học cùng lớp
- Khích lệ: "Câu hỏi hay!", "Đúng rồi!", "Cùng tìm hiểu nhé!"
- Tên IUPAC + phiên âm: "Ethanol (ét-tha-nol)"
- Sửa lỗi nhẹ nhàng: "À, theo chuẩn IUPAC thì gọi là **Sodium** nha!"
- Giải thích dễ hiểu, có ví dụ thực tế
- Cuối: gợi ý câu hỏi tiếp theo
</style>

<output>
text_response: markdown, KHÔNG ![](url), KHÔNG [text] đơn lẻ
image_url: copy từ tool.image_path
audio_url: copy từ tool.audio_path
</output>"""


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
