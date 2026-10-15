# CHEMI – Chatbot Hóa học (API)

CHEMI là backend FastAPI cho chatbot Hóa học THPT, kèm giao diện chat tĩnh. Chatbot trả lời bằng tiếng Việt, dùng danh pháp IUPAC tiếng Anh cho tên chất và nhóm chức, tìm hình ảnh, tạo giọng đọc tiếng Anh và sinh câu hỏi luyện tập.

## Tính năng chính

- Trả lời tiếng Việt, tên chất và nhóm chức theo IUPAC tiếng Anh (Alcohol, Aldehyde, Methane…)
- Nhận câu hỏi dạng văn bản hoặc ảnh
- Tìm hình ảnh (cấu trúc/ảnh thực tế) qua SerpAPI (Google Images)
- TTS tiếng Anh (Groq `canopylabs/orpheus-v1-english`) cho tên chất và đoạn mô tả
- Quiz `mcq`, `matching`, `free_text`, `listening`, mức độ 1–4, soạn bởi Groq `openai/gpt-oss-120b`
- Lưu ngữ cảnh hội thoại theo `thread_id` bằng SQLite checkpoint (`data/checkpoints.db`)

## Yêu cầu

- Python 3.13+ và [uv](https://docs.astral.sh/uv/)
- Biến môi trường:

| Biến | Bắt buộc | Mặc định | Dùng cho |
|---|---|---|---|
| `OPENAI_API_KEY` | có | – | LLM của agent |
| `OPENAI_BASE_URL` | không | `https://gpt3.shupremium.com/v1` | Endpoint tương thích OpenAI |
| `OPENAI_MODEL` | không | `gpt-4.1-mini` | Model của agent |
| `GROQ_API_KEY` | có | – | TTS và soạn quiz |
| `SERPAPI_KEY` | không | – | Tìm ảnh; thiếu thì tool trả về "không tìm thấy hình ảnh" |

Tạo file `.env` ở thư mục gốc:

```env
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://gpt3.shupremium.com/v1
OPENAI_MODEL=gpt-4.1-mini
GROQ_API_KEY=...
SERPAPI_KEY=...
```

## Chạy local

```bash
uv sync
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

Mở http://localhost:8000 để dùng giao diện chat.

## Chạy bằng Docker Compose

```bash
# Yêu cầu: Docker Compose, đã tạo file .env
docker compose up -d --build
```

Compose chạy 3 service:

- `app`: uvicorn 4 worker trên cổng 8000 (chỉ mở trong mạng Docker), có healthcheck `/health`.
- `nginx`: reverse proxy HTTPS cho `chemi.vn` (cấu hình trong `nginx.conf`; đổi domain nếu cần). Giới hạn body 10 MB, timeout đọc 120 s.
- `certbot`: gia hạn chứng chỉ Let's Encrypt mỗi 12 giờ.

Thư mục `./data` trên host được mount vào container. Nó chứa `checkpoints.db` và file âm thanh trong `tts_output/`.

## API

| Endpoint | Mô tả |
|---|---|
| `GET /health` | Kiểm tra trạng thái dịch vụ |
| `GET /` | Giao diện chat (`src/static/index.html`) |
| `POST /query` | Gửi câu hỏi văn bản và/hoặc ảnh |

Request:

```json
{
  "text": "Ancol etylic là gì?",
  "image_base64": null,
  "thread_id": "thread-abc123"
}
```

- `text` hoặc `image_base64` phải có ít nhất một; thiếu cả hai trả về HTTP 400.
- `image_base64` là chuỗi base64 thuần của ảnh PNG/JPEG, không có tiền tố `data:`. Khi có ảnh mà không có `text`, câu hỏi mặc định là "Đây là hợp chất gì?".
- `thread_id` bỏ trống thì server tự tạo (`thread-<hex>`). Dùng lại cùng `thread_id` để giữ ngữ cảnh.

Response (rút gọn):

```json
{
  "success": true,
  "thread_id": "thread-abc123",
  "text_response": "Ethanol là ...",
  "image_base64": "https://.../ethanol-structure.png",
  "audio_base64": "UklGRiQAAABXQVZF...",
  "quiz_data": null,
  "error": null
}
```

- `image_base64` là URL ảnh do SerpAPI trả về.
- `audio_base64` là base64 thuần của file WAV, không có tiền tố `data:`.
- Quá 60 s hoặc agent vượt giới hạn đệ quy (10 bước) trả về `success: false` kèm `error`. Lỗi khác trả về HTTP 500.

### `quiz_data`

Khi người dùng yêu cầu bài tập, `text_response` chỉ là câu dẫn ngắn; nội dung câu hỏi nằm trong `quiz_data`:

```json
{
  "quiz_id": "a1b2c3d4",
  "type": "mcq",
  "level": 1,
  "topic": "alkane",
  "question_text": "Tên IUPAC của CH3-CH2-CH3 là gì?",
  "input_type": "radio",
  "options": ["A) Methane", "B) Ethane", "C) Propane", "D) Butane"],
  "check_method": "exact",
  "correct_answer": "C",
  "explanation": "Propane có 3 nguyên tử carbon..."
}
```

| Trường | Giá trị |
|---|---|
| `type` | `mcq`, `matching`, `free_text`, `listening` |
| `level` | 1 nhận biết, 2 thông hiểu, 3 vận dụng, 4 vận dụng cao |
| `input_type` | `radio` (mcq, listening), `select` (matching), `text` (free_text) |
| `check_method` | `exact`: giao diện tự chấm; `fuzzy`: gửi câu trả lời lên `/query` để agent đánh giá |
| `options` / `match_items` | Phương án cho `radio` / các cặp ghép cho `select` |
| `audio_script` | Chỉ có ở `listening`; agent gọi TTS với nội dung này và trả về qua `audio_base64` |

Với `matching`, `correct_answer` là chuỗi JSON dạng `{"CH4":"Methane",...}`.

## Cấu trúc thư mục

```
.
├─ src/
│  ├─ main.py        # FastAPI: endpoint, đổi file/URL sang base64
│  ├─ agent.py       # Agent LangGraph, system prompt, schema ChemistryResponse/QuizData
│  ├─ tools.py       # Tool: search_image, generate_speech, generate_quiz
│  └─ static/        # Giao diện chat (index.html)
├─ deploy/
│  ├─ setup-ec2.sh   # Cài Docker, Compose, Git trên Amazon Linux 2023
│  └─ init-ssl.sh    # Cấp chứng chỉ Let's Encrypt: ./deploy/init-ssl.sh <domain> <email>
├─ .github/workflows/deploy.yml
├─ docker-compose.yml
├─ Dockerfile
├─ nginx.conf
└─ pyproject.toml / uv.lock
```

## Triển khai

Push lên `main` kích hoạt `.github/workflows/deploy.yml`:

1. SSH vào EC2, lưu commit hiện tại.
2. `git pull` rồi `docker compose up -d --build`.
3. Kiểm tra `http://localhost/health` tối đa 3 lần; thất bại thì `git reset --hard` về commit cũ và build lại.

Secrets cần có: `EC2_SSH_KEY`, `EC2_HOST`.

Thiết lập máy mới: chạy `deploy/setup-ec2.sh`, clone repo, tạo `.env`, chạy `deploy/init-ssl.sh`, rồi `docker compose up -d --build`.

## Ghi chú

- Với tên có số (ví dụ `3-methyl-1-butanol`), TTS cần số viết thành chữ: `three methyl one butanol`. System prompt yêu cầu agent tự chuyển.
- Tên file âm thanh lấy từ 30 ký tự đầu của văn bản và tên giọng đọc, nên hai văn bản trùng 30 ký tự đầu sẽ ghi đè file của nhau.

## Giấy phép

Dùng nội bộ. Nếu cần mở nguồn, hãy thêm giấy phép phù hợp.
