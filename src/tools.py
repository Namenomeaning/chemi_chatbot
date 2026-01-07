"""Các công cụ (tools) cho chatbot hóa học."""

import os
import json
import time
import uuid
import logging
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.tools import tool
from ddgs import DDGS
from groq import Groq

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Audio output directory
AUDIO_OUTPUT_DIR = Path(__file__).parent.parent / "data" / "tts_output"
AUDIO_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Shared Groq client
_groq_client = None


def get_groq_client():
    """Lấy hoặc khởi tạo Groq client."""
    global _groq_client
    if not _groq_client:
        _groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    return _groq_client


@tool
def search_image(keyword: str) -> str:
    """Tìm kiếm hình ảnh hóa học từ Internet (cấu trúc, thực tế, sơ đồ, v.v.).

    Args:
        keyword: Từ khóa tìm kiếm. Ví dụ:
            - "ethanol structure" → công thức cấu tạo
            - "ethanol bottle" → hình ảnh thực tế
            - "ethanol 3d model" → mô hình 3D
            - "chemistry lab" → phòng thí nghiệm

    Returns:
        URL hình ảnh hoặc thông báo lỗi.
    """
    for attempt in range(3):
        try:
            with DDGS() as ddgs:
                if results := list(ddgs.images(query=keyword, max_results=1)):
                    url = results[0]["image"]
                    logger.info(f"Image: {keyword} → {url}")
                    return url
        except Exception as e:
            if attempt < 2:
                time.sleep(2**attempt)
            else:
                return f"Không tìm thấy hình ảnh cho '{keyword}'"
    return f"Không tìm thấy hình ảnh cho '{keyword}'"


@tool
def generate_speech(text: str, voice: str = "autumn") -> str:
    """Tạo âm thanh phát âm cho văn bản.

    Args:
        text: Văn bản cần phát âm
        voice: Giọng nói Orpheus (autumn, breeze, cove, juniper, etc.)

    Returns:
        Đường dẫn tệp audio hoặc thông báo lỗi.
    """
    try:
        client = get_groq_client()
        response = client.audio.speech.create(
            model="canopylabs/orpheus-v1-english",
            voice=voice,
            response_format="wav",
            input=text,
        )

        safe_name = "".join(c if c.isalnum() else "_" for c in text.lower()[:30])
        output_file = AUDIO_OUTPUT_DIR / f"{safe_name}_{voice}.wav"
        response.write_to_file(output_file)

        logger.info(f"Speech: {output_file}")
        return str(output_file)

    except Exception as e:
        return f"Lỗi: Không thể tạo âm thanh - {e}"


# ============== Quiz Generation ==============

QUIZ_SYSTEM_PROMPT = """Bạn là chuyên gia soạn câu hỏi Hóa học THPT Việt Nam (sách Kết nối tri thức).

## NGUYÊN TẮC VÀNG
- Dữ liệu chuẩn > AI thông minh
- NGÔN NGỮ (QUAN TRỌNG):
  + Câu hỏi (question_text) và giải thích (explanation) LUÔN viết bằng tiếng Việt
  + Tên các chất và tên nhóm chức LUÔN dùng IUPAC tiếng Anh
  + Ví dụ ĐÚNG:
    * "Methane là alkane đơn giản nhất" (ĐÚNG)
    * "Ethanol là alcohol bậc 1" (ĐÚNG)
    * "Carboxylic acid có nhóm -COOH" (ĐÚNG)
  + Ví dụ SAI:
    * "Metan là ankan..." (SAI - dùng tiếng Việt hóa)
    * "Ethanol là ancol..." (SAI - dùng "ancol")
    * "Axit cacboxylic có nhóm..." (SAI - dùng "axit cacboxylic")
  + Luôn dùng: Alkane, Alkene, Alkyne, Alcohol, Aldehyde, Ketone, Carboxylic acid, Ester
  + KHÔNG dùng: Ankan, Anken, Ankin, Ancol, Andehit, Xeton, Axit cacboxylic, Este
- Nội dung phải chính xác theo SGK Hóa 10-11-12

## PHẠM VI NỘI DUNG
- Nguyên tố hóa học (bảng tuần hoàn)
- Hợp chất vô cơ (oxit, axit, bazơ, muối)
- Hydrocarbon: Alkane, Alkene, Alkyne, Aromatic
- Dẫn xuất: Alcohol, Aldehyde, Ketone, Carboxylic acid, Ester

## 4 MỨC ĐỘ NHẬN THỨC (Level = độ khó nội dung)

Level và dạng bài là ĐỘC LẬP - bất kỳ dạng bài nào cũng có thể ở bất kỳ level nào.

### Level 1 - NHẬN BIẾT
Đặc điểm: Ghi nhớ, nhận diện tên gọi cơ bản
Ví dụ MCQ: "Tên IUPAC của CH4 là gì?" → [Methane, Ethane, Propane, Butane]
Ví dụ Matching: Ghép CH4↔Methane, C2H6↔Ethane (các chất đơn giản)

### Level 2 - THÔNG HIỂU
Đặc điểm: Hiểu quy tắc đặt tên, phân biệt nhóm chức
Ví dụ MCQ: "Hợp chất nào thuộc nhóm alcohol?" → [Ethanol, Ethane, Ethene, Ethyne]
Ví dụ Listening: Mô tả tính chất đơn giản, đoán chất

### Level 3 - VẬN DỤNG
Đặc điểm: Áp dụng quy tắc gọi tên cho CTCT đơn giản
Ví dụ Free_text: "Gọi tên IUPAC: CH3-CH(CH3)-CH3" → 2-methylpropane
Ví dụ MCQ: "Công thức nào có tên 2-methylpropane?" → [4 CTCT khác nhau]

### Level 4 - VẬN DỤNG CAO
Đặc điểm: Phân tích cấu trúc phức tạp, đồng phân, nhiều nhánh
Ví dụ Free_text: "Gọi tên: CH3-CH(CH3)-CH(C2H5)-CH2-CH3"
Ví dụ MCQ: "Hợp chất nào là 2,3-dimethylbutane?" → [4 CTCT phức tạp]

## CÁCH LEVEL ẢNH HƯỞNG ĐẾN ĐỘ KHÓ TRONG MỖI DẠNG BÀI

| Dạng bài | Level 1 | Level 2 | Level 3 | Level 4 |
|----------|---------|---------|---------|---------|
| MCQ | Chọn tên đúng cho CTPT đơn giản | Phân biệt nhóm chức | Chọn CTCT đúng cho tên | Chọn đáp án cho cấu trúc phức tạp |
| Matching | Ghép chất đơn giản | Ghép theo quy tắc | Ghép CTCT với tên | Ghép nhiều nhóm thế |
| Free_text | Gọi tên chất đơn giản | Giải thích quy tắc | Gọi tên CTCT có nhánh | Gọi tên đa nhánh, đồng phân |
| Listening | Mô tả đơn giản 3-4 câu | Mô tả tính chất 4-5 câu | Mô tả phức tạp 5-6 câu | Mô tả nhiều đặc điểm 6+ câu |

## CẤU TRÚC JSON THEO DẠNG BÀI

### MCQ (level 1-4):
{
  "question_text": "Tên IUPAC của CH3-CH2-CH3 là gì?",
  "input_type": "radio",
  "options": ["A) Methane", "B) Ethane", "C) Propane", "D) Butane"],
  "check_method": "exact",
  "correct_answer": "C",
  "explanation": "Propane có 3 nguyên tử carbon (prop-) và là alkane (-ane). Công thức: C3H8 hay CH3-CH2-CH3."
}

### MATCHING (level 1-4):
{
  "question_text": "Ghép công thức phân tử với tên IUPAC tương ứng:",
  "input_type": "select",
  "match_items": [
    {"left": "CH4", "right_options": ["Methane", "Ethane", "Propane"]},
    {"left": "C2H6", "right_options": ["Methane", "Ethane", "Propane"]},
    {"left": "C3H8", "right_options": ["Methane", "Ethane", "Propane"]}
  ],
  "check_method": "exact",
  "correct_answer": "{\\"CH4\\":\\"Methane\\",\\"C2H6\\":\\"Ethane\\",\\"C3H8\\":\\"Propane\\"}",
  "explanation": "Quy tắc đặt tên alkane: tiền tố chỉ số C (meth=1, eth=2, prop=3) + hậu tố -ane."
}

### FREE_TEXT (level 1-4):
{
  "question_text": "Gọi tên IUPAC của hợp chất: CH3-CH(CH3)-CH2-CH3",
  "input_type": "text",
  "check_method": "fuzzy",
  "correct_answer": "2-methylbutane",
  "accept_variants": ["2-methyl butane", "2-metylbutan"],
  "explanation": "Bước 1: Chọn mạch chính dài nhất (4C = butane). Bước 2: Đánh số từ đầu gần nhánh nhất. Bước 3: Nhánh CH3 ở C-2 → 2-methyl. Kết quả: 2-methylbutane."
}

### LISTENING (level 1-4) - FORMAT "WHO AM I?":
{
  "question_text": "Nghe mô tả bằng tiếng Anh và chọn chất phù hợp:",
  "audio_script": "I am a colorless gas. I am lighter than air. I am the simplest hydrocarbon. My formula has only one carbon atom. Who am I?",
  "input_type": "radio",
  "options": ["A) Methane", "B) Ethane", "C) Propane", "D) Butane"],
  "check_method": "exact",
  "correct_answer": "A",
  "explanation": "Methane (CH4) là hydrocarbon đơn giản nhất với 1 carbon, là khí không màu, nhẹ hơn không khí."
}

## QUY TẮC LISTENING - "WHO AM I?" RIDDLE

### FORMAT BẮT BUỘC:
- Viết NHIỀU câu NGẮN, mỗi câu một đặc điểm
- Kết thúc bằng "Who am I?"
- Giọng điệu như câu đố

### NỘI DUNG ĐƯỢC PHÉP:
✓ Trạng thái: "I am a colorless gas/liquid/solid"
✓ Tính chất: "I am lighter than air", "I dissolve in water"
✓ Công thức (đọc chữ): "My formula is C H 4" (KHÔNG viết CH4)
✓ Ứng dụng: "I am used in beverages", "I am found in natural gas"
✓ Đặc điểm hóa học: "I have one carbon atom", "I contain a hydroxyl group"

### NỘI DUNG BỊ CẤM TUYỆT ĐỐI:
✗ "I am [tên chất]" / "My name is [tên chất]"
✗ "I am called [tên chất]" / "I am known as [tên chất]"
✗ Bất kỳ cách nào tiết lộ tên trực tiếp!

### VÍ DỤ CHUẨN:
Methane: "I am a colorless gas. I am lighter than air. I am the simplest alkane. I have only one carbon atom. I am the main component of natural gas. Who am I?"

Ethanol: "I am a colorless liquid. I have a characteristic smell. My formula is C 2 H 5 O H. I am widely used in beverages and as a disinfectant. Who am I?"

Water: "I am a colorless liquid. I have no taste and no smell. My formula is H 2 O. I cover about 71 percent of Earth's surface. Who am I?"

## PHẢN HỒI SƯ PHẠM (explanation)
- Nếu đúng: Xác nhận + nhắc lại quy tắc
- Nếu sai: Chỉ rõ BƯỚC nào sai, không chỉ nói "sai"

CHỈ trả về JSON, không có text khác."""


@tool
def generate_quiz(question_type: str, topic: str = "random", level: int = 1) -> str:
    """Tạo câu hỏi luyện tập Hóa học.

    Args:
        question_type: Loại câu hỏi - "mcq" | "matching" | "free_text" | "listening"
        topic: Chủ đề (ví dụ: "ethanol", "alkane", "random")
        level: Độ khó 1-4 (1=nhận biết, 2=thông hiểu, 3=vận dụng, 4=nâng cao)

    Returns:
        JSON string chứa cấu trúc quiz hoàn chỉnh.
    """
    level_desc = {
        1: "Nhận biết - câu hỏi đơn giản, trực tiếp",
        2: "Thông hiểu - cần hiểu khái niệm cơ bản",
        3: "Vận dụng - áp dụng kiến thức vào bài toán",
        4: "Nâng cao - hợp chất phức tạp, đồng phân, phức chất"
    }

    prompt = f"""Tạo 1 câu hỏi {question_type.upper()} về "{topic}"
Mức độ: {level_desc.get(level, level_desc[1])}
Chương trình: Hóa học THPT Việt Nam (lớp 10-12)

Trả về JSON theo format đã định. CHỈ JSON, không có text khác."""

    try:
        client = get_groq_client()
        completion = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": QUIZ_SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_completion_tokens=2048,
            top_p=1,
            response_format={"type": "json_object"},
        )
        content = completion.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        quiz_data = json.loads(content)

        # Add metadata
        quiz_data["quiz_id"] = str(uuid.uuid4())[:8]
        quiz_data["type"] = question_type
        quiz_data["level"] = level
        quiz_data["topic"] = topic

        # Set defaults if missing
        if "input_type" not in quiz_data:
            quiz_data["input_type"] = (
                "radio" if question_type in {"mcq", "listening"} else "text"
            )
        if "check_method" not in quiz_data:
            quiz_data["check_method"] = "fuzzy" if question_type == "free_text" else "exact"

        logger.info(f"Quiz generated: {question_type} - {topic} - level {level}")
        return json.dumps(quiz_data, ensure_ascii=False)

    except json.JSONDecodeError as e:
        logger.error(f"Quiz JSON parse error: {e}")
        return json.dumps({"error": f"Lỗi parse JSON: {e}"})
    except Exception as e:
        logger.error(f"Quiz generation error: {e}")
        return json.dumps({"error": f"Lỗi tạo quiz: {e}"})
