"""Extraction node: Extract, expand, and validate chemical query."""

from typing import Dict, Any
from ..state import AgentState
from ..schemas import ExtractionResponse
from ...services import gemini_service
from ...core.logging import setup_logging

logger = setup_logging(__name__)


def extract_and_validate(state: AgentState) -> Dict[str, Any]:
    """Expand query with keywords and validate chemical name/formula.

    Uses rephrased_query from context node (already standalone).

    Args:
        state: Current agent state

    Returns:
        Updated state with search_query, is_valid, and error_message
    """
    # Use rephrased query from context node (already includes conversation context)
    query = state.get("rephrased_query") or state.get("input_text") or "(hình ảnh)"

    # Check if this is an image-only query
    has_image = state.get("input_image") is not None
    is_image_only = has_image and (not state.get("input_text") or query == "(hình ảnh)")

    if is_image_only:
        prompt = """Bạn là chuyên gia nhận dạng cấu trúc phân tử, tuân thủ NGHIÊM NGẶT danh pháp IUPAC.

Phân tích hình cấu trúc phân tử và nhận dạng theo CHUẨN IUPAC quốc tế.

Input: Hình cấu trúc phân tử

Output:
- search_query: Tên IUPAC quốc tế chính thức + công thức (VD: "Ethanol C2H6O" KHÔNG PHẢI "Rượu etylic")
- is_valid: true nếu nhận dạng chính xác được
- error_message: null hoặc mô tả lỗi
"""
    else:
        prompt = f"""Bạn là chuyên gia danh pháp IUPAC quốc tế.

Mở rộng query với keywords CHUẨN IUPAC và kiểm tra tính hợp lệ.

Input: {query}

Yêu cầu:
- Chuyển tên thông thường sang tên IUPAC chuẩn (VD: "Rượu" → "Ethanol", "Metan" → "Methane")
- Chuẩn hóa công thức (VD: "C2H5OH" → "Ethanol C2H6O")
- Thêm ký hiệu nguyên tố nếu hỏi về nguyên tố (VD: "Hydro" → "Hydrogen H")

Output:
- search_query: Tên IUPAC quốc tế chính thức + công thức/ký hiệu
- is_valid: true nếu tên/công thức hợp lệ hoặc có thể chuẩn hóa được
- error_message: Gợi ý sửa nếu hoàn toàn sai, null nếu hợp lệ
"""

    # Call Gemini 2.5 Flash with structured output
    response: ExtractionResponse = gemini_service.generate_structured(
        prompt=prompt,
        response_schema=ExtractionResponse,
        image=state.get("input_image"),
        temperature=0.1
    )

    logger.info(f"Extract & Validate - input: '{query[:50]}...', valid: {response.is_valid}, search_query: '{response.search_query[:50]}...'")

    return {
        "search_query": response.search_query,
        "is_valid": response.is_valid,
        "error_message": response.error_message if not response.is_valid else None
    }
