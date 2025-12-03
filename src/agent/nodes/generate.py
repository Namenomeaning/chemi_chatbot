"""Generation node: Generate final response."""

from typing import Dict, Any
from langchain_core.messages import AIMessage
from ..state import AgentState
from ..schemas import FinalResponse
from ...services import gemini_service
from ...core.logging import setup_logging

logger = setup_logging(__name__)


def generate_response(state: AgentState) -> Dict[str, Any]:
    """Generate final response with RAG context.

    Synthesizes answer from retrieved documents.

    Args:
        state: Current agent state

    Returns:
        Updated state with final_response
    """
    try:
        # Prepare RAG context (minimal schema: type, doc_id, iupac_name, formula, image_path, audio_path)
        rag_text = ""
        rag_context = state.get("rag_context", [])

        if rag_context:
            for i, doc in enumerate(rag_context, 1):
                doc_id = doc.get('doc_id', 'N/A')
                score = doc.get('score', 0.0)
                item_type = doc.get('type', 'unknown')
                rag_text += f"\nKết quả {i} (độ khớp: {score:.2f}):\n"
                rag_text += f"- Tên: {doc.get('iupac_name', 'N/A')}\n"
                rag_text += f"- Công thức: {doc.get('formula', 'N/A')}\n"
                rag_text += f"- Loại: {item_type}\n"
                rag_text += f"- ID: {doc_id}\n"

        prompt = f"""Bạn là chuyên gia Hóa học, LUÔN tuân thủ danh pháp IUPAC quốc tế.

NHIỆM VỤ:
1. Dùng kết quả tìm kiếm để XÁC ĐỊNH chất/nguyên tố
2. Tạo thông tin cơ bản CHÍNH XÁC, tuân thủ NGHIÊM NGẶT chuẩn IUPAC

Input:
- Câu hỏi: {state.get("rephrased_query", "")}
- Kết quả tìm kiếm:{rag_text if rag_text else "\n(Không tìm thấy kết quả)"}

YÊU CẦU NGHIÊM NGẶT:
1. LUÔN dùng tên IUPAC quốc tế chính thức (VD: "Ethanol" KHÔNG PHẢI "Rượu etylic")
2. Công thức phân tử phải CHÍNH XÁC (VD: C2H6O cho Ethanol)
3. Chỉ cung cấp thông tin CƠ BẢN, ĐÚNG CHUẨN:
   - Nguyên tố: Ký hiệu, số nguyên tử, cấu hình electron, vị trí bảng tuần hoàn, tính chất cơ bản
   - Hợp chất: Tên IUPAC, công thức phân tử, công thức cấu tạo, phân loại (ancol, ankan, etc.), tính chất vật lý cơ bản

4. KHÔNG được bịa đặt hoặc suy đoán thông tin không chắc chắn
5. Trả lời bằng tiếng Việt, giải thích NGẮN GỌN, RÕ RÀNG

Nếu KHÔNG tìm thấy → "Xin lỗi, không tìm thấy thông tin về chất này trong cơ sở dữ liệu."

Output:
- text_response: Thông tin cơ bản chính xác (markdown), LUÔN dùng tên IUPAC quốc tế
- selected_doc_id: ID từ kết quả tìm kiếm (null nếu không tìm thấy)
- should_return_image: true nếu hỏi về cấu trúc/công thức/tổng quan
- should_return_audio: true nếu hỏi về phát âm/tên gọi/tổng quan
"""

        # Call Gemini 2.5 Flash with structured output
        logger.info("Generate - calling Gemini API with FinalResponse schema")
        response: FinalResponse = gemini_service.generate_structured(
            prompt=prompt,
            response_schema=FinalResponse,
            temperature=0.3
        )
        logger.info("Generate - Gemini API call succeeded")

        # Get file paths from documents (respect LLM decisions)
        image_path = None
        audio_path = None

        if response.selected_doc_id and rag_context:
            # Find matching document
            for doc in rag_context:
                if doc.get("doc_id") == response.selected_doc_id:
                    # Return local filesystem paths for Gradio
                    if response.should_return_image and doc.get("image_path"):
                        image_path = doc['image_path']
                    if response.should_return_audio and doc.get("audio_path"):
                        audio_path = doc['audio_path']
                    break

        logger.info(f"Generate - selected_doc: '{response.selected_doc_id}', has_image: {bool(image_path)}, has_audio: {bool(audio_path)}")

        # Append assistant's response to conversation history
        return {
            "final_response": {
                "text_response": response.text_response,
                "image_path": image_path,
                "audio_path": audio_path
            },
            "messages": [AIMessage(content=response.text_response)]
        }
    except Exception as e:
        logger.error(f"Generate node error: {str(e)}", exc_info=True)
        raise
