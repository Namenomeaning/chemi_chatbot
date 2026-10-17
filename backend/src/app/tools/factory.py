"""CHEMI tools. Each tool is created with the keys it needs, so no tool reads os.environ.

Each tool returns (content, artifact). The model reads only the content. The server reads the artifact:
{"kind": "image", "url": ...}, {"kind": "audio", "key": ...} or {"kind": "quiz", "data": {...}}.
"""

import json
import logging
import uuid
from urllib.parse import quote

import httpx
from langchain_core.tools import tool

from app.core.config import Settings
from app.prompts import QUIZ_SYSTEM_PROMPT
from app.schemas.quiz import QuizData
from app.services.cloudflare import to_js_bytes

logger = logging.getLogger(__name__)


def make_tools(settings: Settings, bucket):
    base_url = settings.openrouter_base_url
    headers = {"Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}"}

    @tool(response_format="content_and_artifact")
    async def search_image(keyword: str) -> tuple[str, dict | None]:
        """Tìm hình ảnh phù hợp với từ khóa.

        Ví dụ từ khóa: "ethanol structure" (cấu trúc), "ethanol bottle" (hình thực tế),
        "ethanol 3d model" (mô hình 3D), "chemistry lab" (phòng thí nghiệm).
        Hình ảnh được hệ thống tự hiển thị cho người dùng.
        """
        if settings.serpapi_key is None:
            # PubChem supplies chemical structure diagrams without an API key.
            compound = keyword.strip()
            for suffix in (" structure", " 3d model", " 2d", " bottle"):
                compound = compound.removesuffix(suffix)
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    response = await client.get(
                        f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{quote(compound, safe='')}/cids/JSON"
                    )
                    response.raise_for_status()
                    cid = int(response.json()["IdentifierList"]["CID"][0])
                return "Đã tìm thấy cấu trúc từ PubChem.", {
                    "kind": "image",
                    "url": f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/cid/{cid}/PNG",
                }
            except Exception as exc:
                logger.warning("structure_image_failed exception_type=%s", type(exc).__name__)
                return "Không tìm thấy hình ảnh phù hợp.", None
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    "https://serpapi.com/search.json",
                    params={"q": keyword, "tbm": "isch", "api_key": settings.serpapi_key.get_secret_value(), "num": 1},
                )
            response.raise_for_status()
            if images := response.json().get("images_results"):
                return "Đã tìm thấy 1 hình ảnh.", {"kind": "image", "url": images[0].get("original")}
        except Exception as e:
            logger.warning("image_search_failed exception_type=%s", type(e).__name__)
        return f"Không tìm thấy hình ảnh cho '{keyword}'", None

    @tool(response_format="content_and_artifact")
    async def generate_speech(text: str) -> tuple[str, dict | None]:
        """Chuyển văn bản thành giọng đọc tiếng Anh.

        - text: nội dung cần đọc (ví dụ: tên IUPAC, đoạn mô tả)
        - Âm thanh được hệ thống tự phát cho người dùng.
        """
        if bucket is None:
            return "Lỗi: Không thể tạo âm thanh - R2 chưa được bật", None
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.post(
                    f"{base_url}/audio/speech",
                    headers=headers,
                    json={
                        "model": settings.tts_model,
                        "voice": settings.tts_voice,
                        "input": text,
                        "response_format": "mp3",
                    },
                )
            response.raise_for_status()
            key = f"audio/{uuid.uuid4().hex}"
            await bucket.put(key, to_js_bytes(response.content))
            return "Đã tạo âm thanh.", {"kind": "audio", "key": key}
        except Exception as e:
            logger.warning("speech_failed exception_type=%s", type(e).__name__)
            return "Không thể tạo âm thanh lúc này.", None

    @tool(response_format="content_and_artifact")
    async def generate_quiz(question_type: str, topic: str = "random", level: int = 1) -> tuple[str, dict | None]:
        """Tạo câu hỏi luyện tập theo chủ đề và mức độ.

        - question_type: dạng câu hỏi (mcq, matching, free_text, listening)
        - topic: chủ đề (vd: "ethanol", "alkane" hoặc "random")
        - level: độ khó 1–4 (1 dễ – 4 khó)
        - Trả về: chuỗi JSON mô tả nội dung, cấu hình nhập và cách chấm.
          Câu hỏi được hệ thống tự hiển thị cho người dùng.
        """
        if question_type not in {"mcq", "matching", "free_text", "listening"} or level not in range(1, 5):
            return "Quiz type or level is invalid.", None
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
            quiz = QuizData.model_validate(quiz).model_dump()
            return json.dumps(quiz, ensure_ascii=False), {"kind": "quiz", "data": quiz}
        except json.JSONDecodeError as e:
            logger.warning("quiz_parse_failed exception_type=%s", type(e).__name__)
            return json.dumps({"error": "Quiz data was invalid."}), None
        except Exception as e:
            logger.warning("quiz_failed exception_type=%s", type(e).__name__)
            return json.dumps({"error": "Quiz generation is unavailable."}), None

    return [search_image, generate_speech, generate_quiz]
