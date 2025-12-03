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
        prompt = """Bạn là chuyên gia nhận dạng cấu trúc phân tử.

Input: Hình cấu trúc phân tử

Nhiệm vụ: Nhận dạng và trả về TÊN IUPAC duy nhất để search.

Output:
- search_query: CHỈ tên IUPAC (VD: "Ethanol", "Methane")
- is_valid: true nếu nhận dạng được
- error_message: null hoặc lỗi
"""
    else:
        prompt = f"""Bạn là chuyên gia chuẩn hóa tên hóa chất.

Input: {query}

Nhiệm vụ: Chuẩn hóa thành TÊN IUPAC hoặc CÔNG THỨC để search.

Quy tắc chuẩn hóa:
1. Tên tiếng Việt → Tên IUPAC:
   - "Natri" → "Sodium"
   - "Hydro" → "Hydrogen"
   - "Metan" → "Methane"
   - "Rượu" hoặc "Cồn" → "Ethanol"

2. Công thức → Giữ nguyên công thức:
   - "CH4" → "CH4"
   - "C2H5OH" → "C2H5OH"
   - "Na" → "Na"

3. Tên IUPAC → Giữ nguyên:
   - "Ethanol" → "Ethanol"
   - "Sodium" → "Sodium"

Output:
- search_query: Tên IUPAC HOẶC công thức (CHỈ MỘT TRONG HAI, không kết hợp)
- is_valid: true nếu nhận dạng được
- error_message: null hoặc lỗi

VÍ DỤ:
Input: "Natri là gì?" → search_query: "Sodium"
Input: "CH4" → search_query: "CH4"
Input: "Ethanol" → search_query: "Ethanol"
Input: "C2H5OH" → search_query: "C2H5OH"
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
