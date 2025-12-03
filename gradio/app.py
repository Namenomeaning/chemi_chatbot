"""Simple Gradio chatbot interface for Chemistry Chatbot."""

import gradio as gr
import requests
from pathlib import Path

# Configuration
API_URL = "http://localhost:8000/query"
API_URL_UPLOAD = "http://localhost:8000/query/upload"
PROJECT_ROOT = Path(__file__).parent.parent

# Store thread_id globally for conversation context
current_thread_id = None


def respond(message, history):
    """
    Respond to user message.

    Args:
        message: Can be str (text only) or dict with "text" and "files" keys
        history: Chat history (not used, context managed via thread_id)

    Returns:
        str: Response text with markdown for images/audio
    """
    global current_thread_id

    # Extract text and image from message
    user_text = ""
    user_image = None

    if isinstance(message, dict):
        # Multimodal input
        user_text = message.get("text", "").strip()
        user_files = message.get("files", [])
        user_image = user_files[0] if user_files else None
    elif isinstance(message, str):
        # Text only
        user_text = message.strip()

    # Validate input
    if not user_text and not user_image:
        return "❌ Vui lòng nhập câu hỏi hoặc tải lên hình ảnh."

    # Default question for image-only queries
    if not user_text and user_image:
        user_text = "Đây là hợp chất gì?"

    try:
        # Call appropriate API endpoint
        if user_image:
            # Use upload endpoint for multimodal queries
            data = {"text": user_text}
            if current_thread_id:
                data["thread_id"] = current_thread_id

            with open(user_image, "rb") as f:
                files = {"image": f}
                response = requests.post(API_URL_UPLOAD, data=data, files=files, timeout=60)
        else:
            # Use JSON endpoint for text-only queries
            payload = {"text": user_text}
            if current_thread_id:
                payload["thread_id"] = current_thread_id

            response = requests.post(API_URL, json=payload, timeout=60)

        result = response.json()

        if result["success"]:
            # Update thread_id for conversation context
            current_thread_id = result["thread_id"]

            # Format response text
            response_text = result["text_response"]

            # Add image as markdown if available
            if result.get("image_path"):
                image_url = f"http://localhost:8000/files/{result['image_path']}"
                response_text += f"\n\n![Cấu trúc phân tử]({image_url})"

            # Add audio link if available
            if result.get("audio_path"):
                audio_url = f"http://localhost:8000/files/{result['audio_path']}"
                response_text += f"\n\n🔊 [Nghe phát âm]({audio_url})"

            return response_text
        else:
            return f"❌ Lỗi: {result.get('error', 'Unknown error')}"

    except requests.exceptions.ConnectionError:
        return "❌ Không thể kết nối tới backend API. Vui lòng kiểm tra FastAPI server đang chạy."
    except requests.exceptions.Timeout:
        return "❌ Request timeout. Vui lòng thử lại."
    except Exception as e:
        return f"❌ Lỗi: {str(e)}"


def clear_conversation():
    """Clear conversation context."""
    global current_thread_id
    current_thread_id = None
    return None


# Create Gradio interface using ChatInterface
demo = gr.ChatInterface(
    fn=respond,
    title="🧪 Chemistry Chatbot - Trợ lý Hóa học lớp 11",
    description="""
    Hỏi tôi về các hợp chất hóa học! Bạn có thể:
    - Nhập tên hợp chất (VD: "ethanol", "CH4")
    - Upload hình ảnh công thức cấu tạo
    - Hỏi về công thức, phát âm, ứng dụng, v.v.
    """,
    examples=[
        "Ethanol là gì?",
        "Công thức cấu tạo của methane",
        "CH4 phát âm như thế nào?",
        "Ethanol có ứng dụng gì?",
    ],
    multimodal=True,
    chatbot=gr.Chatbot(height=500),
)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Chemistry Chatbot - Starting Gradio Interface")
    print("="*80)

    # Launch with share=True to get public URL
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,  # Creates public gradio.live URL
        show_error=True
    )

    print("\n💡 Tip: Copy the public URL above to share with others!")
    print("="*80 + "\n")
