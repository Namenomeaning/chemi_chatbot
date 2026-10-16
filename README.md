# CHEMI – Chatbot Hóa học

CHEMI là chatbot Hóa học THPT chạy như một Python Worker trên Cloudflare (FastAPI, LangChain, LangGraph), kèm giao diện chat tĩnh. Chatbot trả lời bằng tiếng Việt, dùng danh pháp IUPAC tiếng Anh cho tên chất và nhóm chức, tìm hình ảnh, tạo giọng đọc tiếng Anh và sinh câu hỏi luyện tập.

Nhánh `main` là bản code hiện tại. Nhánh `learn` giữ bản prototype cũ (FastAPI, SQLite, Docker) để học từng bước.

## Kiến trúc

| Thành phần | Dịch vụ Cloudflare |
|---|---|
| API và agent | Python Worker (`backend/src/worker.py`, FastAPI qua ASGI) |
| Bộ nhớ hội thoại theo `thread_id` | D1 (`D1Saver`, bảng `checkpoints` và `writes`) |
| File âm thanh do tool tạo | R2 (`chemi-artifacts`) |
| Giới hạn tốc độ (10 yêu cầu / 60 giây / IP) | Rate Limiting binding `LIMITER` |
| Giao diện chat | Static assets (`backend/static`) |
| Log | Workers Observability |

Agent dùng `create_react_agent` với `langchain<1` và `langgraph<1`. Bản 1.x của `langgraph-checkpoint` cần `ormsgpack`, mà gói này chưa có bản cho Pyodide (môi trường Python của Workers).

## Yêu cầu

- Python 3.13+, [uv](https://docs.astral.sh/uv/) 0.12.3 trở lên (`uv self update`), Node.js
- Tài khoản Cloudflare (để deploy)

| Biến | Bắt buộc | Mặc định | Dùng cho |
|---|---|---|---|
| `OPENAI_API_KEY` | có | – | LLM của agent |
| `OPENAI_BASE_URL` | không | `https://gpt3.shupremium.com/v1` | Endpoint tương thích OpenAI |
| `OPENAI_MODEL` | không | `gpt-4.1-mini` | Model của agent |
| `GROQ_API_KEY` | có | – | TTS và soạn quiz |
| `SERPAPI_KEY` | không | – | Tìm ảnh |

## Chạy local

```bash
cd backend
npm install
cp .dev.vars.example .dev.vars   # điền OPENAI_API_KEY và GROQ_API_KEY
npx wrangler d1 execute chemi --local --file schema.sql
uv run pywrangler dev
```

Mở http://localhost:8787 để dùng giao diện chat. Kiểm tra nhanh:

```bash
curl localhost:8787/health
curl -X POST localhost:8787/query -H 'content-type: application/json' -d '{"text":"Ethanol là gì?"}'
```

## Deploy

```bash
cd backend
npx wrangler login
npx wrangler d1 create chemi                 # chép database_id vào wrangler.jsonc
npx wrangler r2 bucket create chemi-artifacts
npx wrangler d1 execute chemi --remote --file schema.sql
npx wrangler secret put OPENAI_API_KEY
npx wrangler secret put GROQ_API_KEY
npx wrangler secret put SERPAPI_KEY          # tùy chọn
uv run pywrangler deploy
```

Domain `chemi.quangiz.me` đã khai báo trong `routes` của `wrangler.jsonc` (zone `quangiz.me` phải nằm trong cùng tài khoản Cloudflare). R2 đang tắt: bật R2 trong dashboard, tạo bucket `chemi-artifacts`, rồi bỏ comment `r2_buckets` để dùng giọng đọc.

## Trạng thái kiểm thử

- Đã chạy local với server OpenAI giả: `/health`, `/ready`, `POST /query` (agent + D1), trang chat, bộ nhớ trong D1.
- Đã deploy: `https://chemi.quangiz.me` trả `/health`, `/ready` và trang chat.
- Chưa chạy: gọi LLM thật, TTS và quiz (Groq), tìm ảnh (SerpAPI). `POST /query` trả 503 cho tới khi đặt secret `OPENAI_API_KEY` và `GROQ_API_KEY`.
