"""CHEMI tools. Each tool is created with the keys it needs, so no tool reads os.environ."""
import json
import logging
import re
import uuid

import httpx
from langchain_core.tools import tool

from app.core.config import Settings
from app.prompts import QUIZ_SYSTEM_PROMPT
from app.services.cloudflare import to_js_bytes

logger = logging.getLogger(__name__)

AUDIO_ID = re.compile(r"^audio/[0-9a-f]{32}$")


def make_tools(settings: Settings, bucket):
    base_url = settings.openrouter_base_url
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"}

    @tool
    async def search_image(keyword: str) -> str:
        """Tìm hình ảnh phù hợp với từ khóa.

        Ví dụ từ khóa: "ethanol structure" (cấu trúc), "ethanol bottle" (hình thực tế),
        "ethanol 3d model" (mô hình 3D), "chemistry lab" (phòng thí nghiệm).
        Trả về URL hình ảnh hoặc thông báo lỗi.
        """
        if settings.serpapi_key is None:
            return f"Không tìm thấy hình ảnh cho '{keyword}' (missing API key)"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://serpapi.com/search.json",
                    params={"q": keyword, "tbm": "isch", "api_key": settings.serpapi_key.get_secret_value(), "num": 1},
                )
            response.raise_for_status()
            if images := response.json().get("images_results"):
                return images[0].get("original")
        except Exception as e:
            logger.error("Image search error: %s", e)
        return f"Không tìm thấy hình ảnh cho '{keyword}'"

    @tool
    async def generate_speech(text: str) -> str:
        """Chuyển văn bản thành giọng đọc tiếng Anh.

        - text: nội dung cần đọc (ví dụ: tên IUPAC, đoạn mô tả)
        - Kết quả: mã âm thanh dạng audio/<id>. Điền mã này vào audio_url.
        """
        if bucket is None:
            return "Lỗi: Không thể tạo âm thanh - R2 chưa được bật"
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{base_url}/audio/speech",
                    headers=headers,
                    json={"model": settings.tts_model, "voice": settings.tts_voice, "input": text, "response_format": "mp3"},
                )
            response.raise_for_status()
            key = f"audio/{uuid.uuid4().hex}"
            await bucket.put(key, to_js_bytes(response.content))
            return key
        except Exception as e:
            return f"Lỗi: Không thể tạo âm thanh - {e}"

    @tool
    async def generate_quiz(question_type: str, topic: str = "random", level: int = 1) -> str:
        """Tạo câu hỏi luyện tập theo chủ đề và mức độ.

        - question_type: dạng câu hỏi (mcq, matching, free_text, listening)
        - topic: chủ đề (vd: "ethanol", "alkane" hoặc "random")
        - level: độ khó 1–4 (1 dễ – 4 khó)
        - Trả về: chuỗi JSON mô tả nội dung, cấu hình nhập và cách chấm
        """
        level_desc = {
            1: "Nhận biết - câu hỏi đơn giản, trực tiếp",
            2: "Thông hiểu - cần hiểu khái niệm cơ bản",
            3: "Vận dụng - áp dụng kiến thức vào bài toán",
            4: "Nâng cao - hợp chất phức tạp, đồng phân, phức chất",
        }
        prompt = (
            f'Tạo 1 câu hỏi {question_type.upper()} về "{topic}"\n'
            f"Mức độ: {level_desc.get(level, level_desc[1])}\n"
            "Chương trình: Hóa học THPT Việt Nam (lớp 10-12)\n\n"
            "Trả về JSON theo format đã định. CHỈ JSON, không có text khác."
        )
        try:
            async with httpx.AsyncClient(timeout=40) as client:
                response = await client.post(
                    f"{base_url}/chat/completions",
                    headers=headers,
                    json={
                        "model": settings.quiz_model,
                        "messages": [
                            {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
                            {"role": "user", "content": prompt},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 2048,
                        "response_format": {"type": "json_object"},
                    },
                )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"].strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
            quiz = json.loads(content)
            quiz["quiz_id"] = uuid.uuid4().hex[:8]
            quiz["type"] = question_type
            quiz["level"] = level
            quiz["topic"] = topic
            quiz.setdefault("input_type", "radio" if question_type in {"mcq", "listening"} else "text")
            quiz.setdefault("check_method", "fuzzy" if question_type == "free_text" else "exact")
            return json.dumps(quiz, ensure_ascii=False)
        except json.JSONDecodeError as e:
            logger.error("Quiz JSON parse error: %s", e)
            return json.dumps({"error": f"Lỗi parse JSON: {e}"})
        except Exception as e:
            logger.error("Quiz generation error: %s", e)
            return json.dumps({"error": f"Lỗi tạo quiz: {e}"})

    return [search_image, generate_speech, generate_quiz]
