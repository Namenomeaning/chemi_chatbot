"""CHEMI - Modern Chemistry Chatbot Interface with Gradio Blocks."""

import os
import gradio as gr
import requests
from pathlib import Path

# Configuration - Auto-detect GitHub Codespaces or use environment variable
def get_base_url():
    """Get API base URL - auto-detect Codespaces or use localhost."""
    if os.getenv("API_BASE_URL"):
        return os.getenv("API_BASE_URL")

    # Auto-detect GitHub Codespaces
    codespace_name = os.getenv("CODESPACE_NAME")
    github_codespaces_port_forwarding_domain = os.getenv("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN")

    if codespace_name and github_codespaces_port_forwarding_domain:
        return f"https://{codespace_name}-8000.{github_codespaces_port_forwarding_domain}"

    return "http://localhost:8000"

BASE_URL = get_base_url()
API_URL = f"{BASE_URL}/query"
API_URL_UPLOAD = f"{BASE_URL}/query/upload"
PROJECT_ROOT = Path(__file__).parent.parent

# Store uploaded image path temporarily
uploaded_image_path = None


def user_message(message, history):
    """Add user message to history.

    Args:
        message: Can be str (text only) or dict with "text" and "files" keys
        history: Chat history list

    Returns:
        tuple: ("", updated_history) - empty string clears input box
    """
    # Extract text from message
    if isinstance(message, dict):
        user_text = message.get("text", "").strip()
        user_files = message.get("files", [])
        # Show image indicator in chat if file uploaded
        if user_files and not user_text:
            user_text = "📷 [Hình ảnh công thức]"
        elif user_files and user_text:
            user_text = f"{user_text} 📷"
    else:
        user_text = message.strip()

    # Append user message to history
    return "", history + [[user_text, None]]


def bot_response(history):
    """Generate bot response and update history.

    Args:
        history: Chat history list

    Yields:
        Updated history with bot response
    """
    global uploaded_image_path

    # Get last user message
    user_message_text = history[-1][0]

    # Extract actual text (remove image indicators)
    user_text = user_message_text.replace("📷 [Hình ảnh công thức]", "").replace(" 📷", "").strip()

    # Validate input
    if not user_text and not uploaded_image_path:
        history[-1][1] = "⚠️ Vui lòng nhập câu hỏi hoặc tải lên hình ảnh."
        yield history
        return

    # Default question for image-only queries
    if not user_text and uploaded_image_path:
        user_text = "Đây là hợp chất gì?"

    try:
        # Call appropriate API endpoint
        if uploaded_image_path:
            # Use upload endpoint for multimodal queries
            data = {"text": user_text}

            with open(uploaded_image_path, "rb") as f:
                files = {"image": f}
                response = requests.post(API_URL_UPLOAD, data=data, files=files, timeout=60)

            # Clear uploaded image after use
            uploaded_image_path = None
        else:
            # Use JSON endpoint for text-only queries
            payload = {"text": user_text}
            response = requests.post(API_URL, json=payload, timeout=60)

        result = response.json()

        if result["success"]:
            # Format response text
            response_text = result["text_response"]

            # Add image (URL or base64)
            if result.get("image_base64"):
                image_data = result["image_base64"]
                if image_data.startswith(("http://", "https://")):
                    image_uri = image_data
                else:
                    image_uri = f"data:image/png;base64,{image_data}"
                response_text += f"\n\n![Cấu trúc phân tử]({image_uri})"

            # Add audio (URL or base64)
            if result.get("audio_base64"):
                audio_data = result["audio_base64"]
                if audio_data.startswith(("http://", "https://")):
                    audio_uri = audio_data
                else:
                    audio_uri = f"data:audio/wav;base64,{audio_data}"
                response_text += f"\n\n<audio controls src=\"{audio_uri}\">🔊 Nghe phát âm</audio>"

            history[-1][1] = response_text
        else:
            history[-1][1] = f"❌ **Lỗi:** {result.get('error', 'Unknown error')}"

    except requests.exceptions.ConnectionError:
        history[-1][1] = "❌ **Không thể kết nối tới backend.** Vui lòng kiểm tra FastAPI server đang chạy."
    except requests.exceptions.Timeout:
        history[-1][1] = "⏱️ **Timeout:** Request mất quá nhiều thời gian. Vui lòng thử lại."
    except Exception as e:
        history[-1][1] = f"❌ **Lỗi không mong muốn:** {str(e)}"

    yield history


def clear_conversation():
    """Clear conversation history."""
    return []


# Custom CSS for modern look
custom_css = """
#title {
    text-align: center;
    font-size: 3em;
    font-weight: 700;
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin-bottom: 0.5em;
}

#subtitle {
    text-align: center;
    font-size: 1.2em;
    color: #666;
    margin-bottom: 1.5em;
}

#description {
    text-align: center;
    padding: 1em;
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    border-radius: 10px;
    margin-bottom: 1em;
}

.example-btn {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    border: none;
    border-radius: 8px;
    padding: 0.5em 1em;
    cursor: pointer;
    transition: all 0.3s ease;
}

.example-btn:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);
}

#footer {
    text-align: center;
    padding: 1em;
    color: #999;
    font-size: 0.9em;
    margin-top: 1em;
}

#chatbot {
    border-radius: 15px;
    box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}
"""

# Build interface with Blocks for full customization
with gr.Blocks(css=custom_css, title="CHEMI - Trợ lý Hóa học") as demo:
    # Header
    gr.Markdown(
        """
        <div id="title">🧪 CHEMI</div>
        <div id="subtitle">Trợ lý Hóa học thông minh cho học sinh</div>
        """,
        elem_id="title-section"
    )

    # Description
    gr.Markdown(
        """
        <div id="description">
        <strong>✨ CHEMI giúp bạn khám phá thế giới Hóa học!</strong><br>
        💬 Hỏi về tên hợp chất, công thức, tính chất, ứng dụng<br>
        📷 Upload hình ảnh công thức cấu tạo để nhận dạng<br>
        🔊 Nghe phát âm chuẩn của các tên hóa học quốc tế
        </div>
        """
    )

    # Main chat interface
    chatbot = gr.Chatbot(
        value=[],
        height=500,
        show_label=False,
        avatar_images=(None, "https://em-content.zobj.net/source/twitter/376/test-tube_1f9ea.png"),
        elem_id="chatbot",
        bubble_full_width=False,
    )

    with gr.Row():
        with gr.Column(scale=9):
            msg = gr.MultimodalTextbox(
                show_label=False,
                placeholder="Nhập câu hỏi về Hóa học hoặc upload hình công thức...",
                file_types=["image"],
                submit_btn="Gửi",
            )
        with gr.Column(scale=1, min_width=100):
            clear = gr.Button("🗑️ Xóa hội thoại", variant="secondary")

    # Example questions
    gr.Markdown("### 💡 Câu hỏi mẫu (click để thử):")
    with gr.Row():
        example_1 = gr.Button("Ethanol là gì?", size="sm")
        example_2 = gr.Button("Công thức cấu tạo của Methane?", size="sm")
        example_3 = gr.Button("CH₄ phát âm thế nào?", size="sm")
        example_4 = gr.Button("Cho tôi thông tin về Natri", size="sm")

    # Footer
    gr.Markdown(
        """
        <div id="footer">
        Powered by Google Gemini 2.5 Flash & LangGraph |
        Data: 118 nguyên tố + 7 hợp chất Hóa học lớp 11
        </div>
        """
    )

    # Event handlers - chain user input and bot response
    msg.submit(user_message, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot_response, chatbot, chatbot
    )
    clear.click(clear_conversation, None, [chatbot], queue=False)

    # Example button handlers
    example_1.click(lambda: "Ethanol là gì?", None, msg)
    example_2.click(lambda: "Công thức cấu tạo của Methane?", None, msg)
    example_3.click(lambda: "CH₄ phát âm thế nào?", None, msg)
    example_4.click(lambda: "Cho tôi thông tin về Natri", None, msg)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 CHEMI - Chemistry Chatbot")
    print("="*80)
    print(f"🌐 API Backend: {BASE_URL}")
    print("🚀 Starting Gradio Interface...")
    print("="*80 + "\n")

    # Launch with share=True to get public URL
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_error=True
    )

    print("\n💡 Tip: Copy the public URL above to share with others!")
    print("="*80 + "\n")
