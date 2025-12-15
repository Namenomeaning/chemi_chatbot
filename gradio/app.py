"""CHEMI - Simple Chemistry Chatbot Interface."""

import os
import re
import random
import gradio as gr
import requests
from pathlib import Path

# Welcome greetings for CHEMI
WELCOME_GREETINGS = [
    "Chào bạn! 👋 Hôm nay bạn có câu hỏi Hóa học gì cho CHEMI không? 🧪",
    "Xin chào! 🎉 CHEMI sẵn sàng giúp bạn học Hóa học. Bạn muốn tìm hiểu về chất nào?",
    "Hello! 👋 Mình là CHEMI - trợ lý Hóa học của bạn. Hỏi mình về nguyên tố, hợp chất, hay upload hình công thức nhé!",
    "Chào bạn! 🧬 CHEMI đây! Bạn cần tra cứu về Sodium, Ethanol hay chất nào khác?",
    "Hi! 😊 CHEMI sẵn sàng giúp bạn học danh pháp IUPAC. Thử hỏi 'Natri là gì?' xem nào!",
    "Xin chào! 🔬 Hôm nay CHEMI có thể giúp gì cho bạn? Nhập tên/công thức hoặc upload hình ảnh cấu trúc phân tử nhé!",
    "Chào bạn! ⚗️ CHEMI ở đây để giúp bạn với Hóa học lớp 11. Bạn muốn tìm hiểu về chất nào?",
    "Hello! 🧪 Mình là CHEMI. Hỏi mình về cách phát âm tên IUPAC, cấu trúc phân tử, hay bất cứ điều gì về Hóa học nhé!",
]


def get_welcome_message():
    """Get a random welcome greeting."""
    return random.choice(WELCOME_GREETINGS)

# Custom CSS - Dark Mode Modern Theme
CUSTOM_CSS = """
/* ===== HEADER ===== */
.header-container {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%) !important;
    border: 1px solid #334155 !important;
    padding: 20px 24px !important;
    border-radius: 16px !important;
    margin: 0 !important;
}

.header-container h1 {
    background: linear-gradient(90deg, #22d3ee, #a78bfa, #f472b6) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    margin: 0 0 4px 0 !important;
    font-size: 1.6em !important;
    font-weight: 700 !important;
}

.header-container p {
    color: #64748b !important;
    margin: 0 !important;
    font-size: 0.85em !important;
}

/* ===== NEW CHAT BUTTON ===== */
.new-chat-btn {
    background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
    border: none !important;
    border-radius: 12px !important;
    font-weight: 600 !important;
    font-size: 0.9em !important;
    padding: 12px 16px !important;
    margin-top: 8px !important;
    box-shadow: 0 4px 12px rgba(5, 150, 105, 0.3) !important;
    transition: all 0.2s ease !important;
}

.new-chat-btn:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 16px rgba(5, 150, 105, 0.4) !important;
}

/* ===== CHATBOT AREA ===== */
.chatbot-container {
    border: 1px solid #334155 !important;
    border-radius: 16px !important;
    background: #0f172a !important;
    margin-top: 16px !important;
}

/* ===== INPUT BOX ===== */
.input-box {
    margin-top: 16px !important;
}

/* ===== QUICK EXAMPLES ===== */
.examples-row {
    margin-top: 12px !important;
}

.quick-examples {
    color: #64748b !important;
    font-size: 0.82em !important;
    text-align: center;
}

.quick-examples span {
    color: #94a3b8;
    background: #1e293b;
    padding: 4px 10px;
    border-radius: 12px;
    margin: 0 2px;
    border: 1px solid #334155;
}

/* ===== MESSAGE BUBBLES ===== */
.message, .bot, .user {
    max-width: 85% !important;
}

/* ===== IMAGES IN CHAT ===== */
.message img, [data-testid="bot"] img, [data-testid="user"] img {
    max-width: 200px !important;
    max-height: 200px !important;
    border-radius: 10px;
    margin-top: 10px;
    border: 1px solid #334155;
    background: #1e293b;
    padding: 6px;
    object-fit: contain;
    display: block !important;
}

/* ===== AUDIO ===== */
audio {
    width: 280px !important;
    max-width: 280px !important;
    margin-top: 12px;
    border-radius: 8px;
    display: block;
}
"""


BASE_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
API_URL = f"{BASE_URL}/query"
API_URL_UPLOAD = f"{BASE_URL}/query/upload"

# Store uploaded image path and thread_id temporarily
uploaded_image_path = None
current_thread_id = None


def image_to_base64_uri(file_path: str) -> str:
    """Convert image file to base64 data URI."""
    import base64
    import mimetypes

    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = "image/png"

    with open(file_path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")

    return f"data:{mime_type};base64,{data}"


def user_message(message, history):
    """Add user message to history (Gradio 6.0 format)."""
    global uploaded_image_path

    # Extract text and files from MultimodalTextbox
    if isinstance(message, dict):
        user_text = message.get("text", "").strip()
        user_files = message.get("files", [])

        # Store image path for bot_response to use (files are dict with "path" key)
        if user_files:
            # Extract path from file object dict
            file_obj = user_files[0]
            uploaded_image_path = file_obj.get("path") if isinstance(file_obj, dict) else file_obj

            # Display image in chat with text
            if not user_text:
                user_text = "Đây là hợp chất gì?"

            # Convert image to base64 for inline display
            image_uri = image_to_base64_uri(uploaded_image_path)
            content = f"{user_text}\n\n![image]({image_uri})"
        else:
            uploaded_image_path = None
            content = user_text
    else:
        user_text = str(message).strip()
        uploaded_image_path = None
        content = user_text

    # Gradio 6.0 format: dict with role and content
    history.append({"role": "user", "content": content})
    return "", history


def bot_response(history):
    """Generate bot response and update history (Gradio 6.0 format)."""
    global uploaded_image_path, current_thread_id

    # Get last user message (Gradio 6.0 format)
    last_message = history[-1]
    user_message_content = last_message["content"]

    # Extract text from content (remove markdown image if present)
    if isinstance(user_message_content, str):
        # Remove markdown image syntax: ![text](data:...)
        user_text = re.sub(r'\n*!\[.*?\]\(data:.*?\)', '', user_message_content).strip()
    else:
        user_text = str(user_message_content)

    if not user_text and not uploaded_image_path:
        history.append({"role": "assistant", "content": "⚠️ Vui lòng nhập câu hỏi hoặc tải lên hình ảnh."})
        yield history
        return

    if not user_text and uploaded_image_path:
        user_text = "Đây là hợp chất gì?"

    try:
        if uploaded_image_path:
            data = {
                "text": user_text,
                "thread_id": current_thread_id  # Pass thread_id for conversation context
            }
            with open(uploaded_image_path, "rb") as f:
                files = {"image": f}
                response = requests.post(API_URL_UPLOAD, data=data, files=files, timeout=60)
            uploaded_image_path = None
        else:
            payload = {
                "text": user_text,
                "thread_id": current_thread_id  # Pass thread_id for conversation context
            }
            response = requests.post(API_URL, json=payload, timeout=60)

        # Debug: Check response status and content
        if response.status_code != 200:
            history.append({"role": "assistant", "content": f"❌ **API Error (HTTP {response.status_code}):**\n```\n{response.text[:500]}\n```\n\n💡 Kiểm tra FastAPI backend đang chạy tại: `{BASE_URL}`"})
            yield history
            return

        # Check if response is JSON
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            history.append({"role": "assistant", "content": f"❌ **API không trả về JSON** (Content-Type: {content_type})\n\n💡 Kiểm tra:\n1. FastAPI backend chạy chưa?\n2. Port 8000 đã public chưa? (Codespaces)\n3. API URL: `{BASE_URL}`"})
            yield history
            return

        result = response.json()

        # Store thread_id from response for next request
        if result.get("thread_id"):
            current_thread_id = result["thread_id"]

        if result["success"]:
            response_text = result["text_response"]

            if result.get("image_base64"):
                image_data = result["image_base64"]
                if image_data.startswith(("http://", "https://")):
                    image_uri = image_data
                else:
                    image_uri = f"data:image/png;base64,{image_data}"
                response_text += f"\n\n![Cấu trúc phân tử]({image_uri})"

            if result.get("audio_base64"):
                audio_data = result["audio_base64"]
                if audio_data.startswith(("http://", "https://")):
                    audio_uri = audio_data
                else:
                    audio_uri = f"data:audio/wav;base64,{audio_data}"
                response_text += f"\n\n<audio controls src=\"{audio_uri}\">🔊 Nghe phát âm</audio>"

            history.append({"role": "assistant", "content": response_text})
        else:
            history.append({"role": "assistant", "content": f"❌ **Lỗi:** {result.get('error', 'Unknown error')}"})

    except requests.exceptions.ConnectionError:
        history.append({"role": "assistant", "content": "❌ **Không thể kết nối tới backend.** Vui lòng kiểm tra FastAPI server đang chạy."})
    except requests.exceptions.Timeout:
        history.append({"role": "assistant", "content": "⏱️ **Timeout:** Request mất quá nhiều thời gian. Vui lòng thử lại."})
    except Exception as e:
        history.append({"role": "assistant", "content": f"❌ **Lỗi không mong muốn:** {str(e)}"})

    yield history


def get_initial_history():
    """Get initial chat history with welcome message."""
    return [{"role": "assistant", "content": get_welcome_message()}]


def clear_conversation():
    """Clear conversation history and reset thread_id with new welcome message."""
    global current_thread_id
    current_thread_id = None  # Reset thread_id to start new conversation
    return get_initial_history()


# Gradio interface
with gr.Blocks() as demo:
    # Inject custom CSS
    gr.HTML(f"<style>{CUSTOM_CSS}</style>")

    # Header with clear button
    with gr.Row():
        with gr.Column(scale=9, elem_classes="header-container"):
            gr.Markdown(
                """
                # ⚗️ CHEMI - Trợ lý Hóa học
                Hỏi về nguyên tố, hợp chất · Nhập tên/công thức hoặc upload hình ảnh
                """
            )
        with gr.Column(scale=1, min_width=80):
            clear = gr.Button("🔄 Mới", elem_classes="new-chat-btn")

    # Chat area
    chatbot = gr.Chatbot(
        value=get_initial_history(),
        height=450,
        show_label=False,
        avatar_images=(
            None,  # User avatar
            "https://em-content.zobj.net/source/twitter/408/test-tube_1f9ea.png"  # Bot avatar
        ),
        elem_classes="chatbot-container"
    )

    # Input area - clean single textbox
    msg = gr.MultimodalTextbox(
        placeholder="💬 Nhập câu hỏi hoặc upload hình ảnh...",
        file_count="single",
        show_label=False,
        elem_classes="input-box"
    )

    # Quick examples as chips
    gr.Markdown(
        """
        <div class="quick-examples">
            💡 <span>Ethanol là gì?</span> · <span>Sodium</span> · <span>CH4</span> · <span>Upload ảnh</span>
        </div>
        """,
        elem_classes="examples-row"
    )

    msg.submit(user_message, [msg, chatbot], [msg, chatbot], queue=False).then(
        bot_response, chatbot, chatbot
    )
    clear.click(clear_conversation, None, [chatbot], queue=False)


if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 CHEMI - Chemistry Chatbot")
    print("="*80)
    print(f"🌐 API Backend: {BASE_URL}")
    print(f"   - Query endpoint: {API_URL}")
    print(f"   - Upload endpoint: {API_URL_UPLOAD}")
    print("")
    print("⚠️  Trên GitHub Codespaces:")
    print("   1. Chạy FastAPI: uv run uvicorn main:app --host 0.0.0.0 --port 8000")
    print("   2. Set port 8000 visibility = Public")
    print("="*80)
    print("🚀 Starting Gradio Interface...")
    print("="*80 + "\n")

    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=True,
        show_error=True
    )

    print("\n💡 Tip: Copy the public URL above to share with others!")
    print("="*80 + "\n")
