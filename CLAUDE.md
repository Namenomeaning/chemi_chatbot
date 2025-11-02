# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Chemistry Chatbot for Grade 11 Vietnamese students - an AI agent that accepts chemical images or international names (IUPAC/common), validates naming correctness, retrieves compound information from RAG, and outputs detailed explanations, structure images, and audio pronunciation.

**Tech Stack:**
- Python 3.10+
- LangGraph (orchestration)
- Google Gemini 2.5 Flash (LLM/VQA) via `google-genai` package
- Qwen/Qwen2.5-Embedding-0.6B (multilingual embeddings)
- Qdrant 1.8.0+ (vector database, local Docker)
- Piper TTS (open-source, offline, CPU-optimized)
- FastAPI (backend API)
- Gradio (frontend prototyping)

**Package Manager:** UV (use `uv` for all Python operations)

## Development Commands

### Environment Setup
```bash
# Install dependencies
uv sync

# Or install from requirements.txt
uv pip install -r requirements.txt

# Run Qdrant locally (Docker Compose)
docker compose up -d

# Check Qdrant is running
curl http://localhost:6333/health
```

### Running the Application
```bash
# Run ingestion script to populate vector database
uv run src/ingest.py

# Run FastAPI backend (when implemented)
uv run uvicorn main:app --reload

# Run Gradio frontend (when implemented)
uv run python app.py
```

### Testing
```bash
# Run tests
uv run pytest

# Run specific test file
uv run pytest tests/test_rag.py

# Run with coverage
uv run pytest --cov=. --cov-report=html
```

## Architecture

### RAG Pipeline (4-stage workflow)

**Stage 1: Data Foundation (RAG Knowledge Base)**
- JSON documents stored in `data/` directory
- Each compound has: doc_id, iupac_name, common_names, formula, molecular_formula, class, image_path, audio_path, info, naming_rule
- Audio files pre-generated via `src/generate_tts.py` using Piper TTS (offline, open-source)
- General rules stored in separate documents (e.g., `rules_alkane.json`, `classification.json`)

**Stage 2: LangGraph Flow (4 nodes, sequential)**

State definition:
```python
class AgentState(TypedDict):
    input_text: Optional[str]
    input_image: Optional[bytes]
    processed_query: str
    is_name_correct: bool
    corrected_name: Optional[str]
    rag_context: List[dict]
    final_response: dict
```

Node sequence:
1. `extract_chemical_query` - Uses Gemini to extract chemical name/formula from text/image
2. `validate_chemical_name` - Validates international name correctness against chemistry rules, provides correction if near-match found
3. `retrieve_from_rag` - Hybrid search: embeds query with Qwen2.5 (dense) + BM25 tokenization (sparse), retrieves top K=3 documents from Qdrant using weighted fusion
4. `generate_response` - Uses Gemini to synthesize answer, returns JSON with `text_response`, `image_path`, `audio_path` (all from RAG context)

Graph edges: START → extract → validate → retrieve → generate → END

**Stage 3: Vector Database (Hybrid Search)**
- Qdrant 1.8.0+ running locally via Docker Compose with hybrid search enabled
- **Dense retrieval:** Qwen/Qwen2.5-Embedding-0.6B (896 dimensions) for semantic search (multilingual VI/EN)
- **Sparse retrieval:** BM25 tokenization for exact formula matching (C2H5OH, CH3-CH2-OH, etc.)
- Collection stores both dense vectors and sparse vectors with full JSON as payload
- Ingestion: `src/ingest.py` reads all JSON files, creates dense + sparse embeddings, uploads to Qdrant
- Query time: Combine dense + sparse scores with weighted fusion (default: 0.7 dense + 0.3 sparse)

**Stage 4: API Layer**
- FastAPI endpoints receive text/image input
- Invoke LangGraph workflow
- Return JSON response with text, image URL, audio URL

**Stage 5: Frontend**
- Gradio UI with text input, image uploader, submit button
- Displays response text (markdown), structure image, audio player
- Simple interface: `gr.Interface` or `gr.Blocks` for multi-modal input/output

## Code Standards

### Naming Conventions
- **Production-level names:** Clear, descriptive, follow Python PEP 8
- **Functions:** `snake_case`, verb-based (e.g., `extract_chemical_query`, `retrieve_from_rag`)
- **Classes:** `PascalCase` (e.g., `AgentState`, `ChemicalDocument`)
- **Constants:** `UPPER_SNAKE_CASE` (e.g., `QDRANT_HOST`, `EMBEDDING_MODEL_NAME`)

### Documentation
- **Docstrings:** Google style, production-level quality
- **Type hints:** Required for all function signatures
- **Comments:** Only for non-obvious logic; avoid redundant comments

### Code Quality
- **No over-engineering:** Only create functions that are actually used
- **No redundant code:** Avoid speculative abstractions
- **Context-aware:** Always check latest docs (use web search/fetch) before implementing libraries or APIs

### Python Execution
- **Always use UV:** `uv run <script.py>` or `uv pip install <package>`
- Never use `python` or `pip` directly

## Important Files

### Data Schema (`data/*.json`)

Simplified structure for compounds:
```json
{
  "doc_id": "ethanol",
  "iupac_name": "Ethanol",
  "common_names": ["Rượu etylic", "Ancol etylic", "Cồn", "Ethyl alcohol"],
  "formula": "C2H5OH",
  "molecular_formula": "C2H6O",
  "class": "Ancol (Alcohol)",
  "image_path": "images/ethanol.png",
  "audio_path": "audio_output/ethanol.wav",
  "info": "Ethanol là ancol đơn chức bậc 1, chất lỏng không màu, tan vô hạn trong nước.",
  "naming_rule": "Tên hydrocarbon tương ứng (ethane) + hậu tố '-ol' → ethanol"
}
```

**Key points:**
- Single level fields (no nested objects)
- `image_path` for structure images, `audio_path` for pre-generated TTS
- Combined common names in one array (Vietnamese and English)
- Essential fields only: names, formulas, class, image, audio, description, naming rule

### LangGraph Prompts (All in Vietnamese)

**Node 1 (extract_chemical_query):**
- Input: text and/or image
- Prompt: "Bạn là chuyên gia hóa học. Phân tích văn bản và/hoặc hình ảnh được cung cấp. Nhiệm vụ của bạn là xác định chính xác tên (IUPAC, thông thường) hoặc công thức hóa học (CTPT, CTCT) mà người dùng đang hỏi. Chỉ trả về chuỗi văn bản duy nhất là tên hoặc công thức đó."

**Node 2 (validate_chemical_name):**
- Input: processed_query
- Prompt: "Bạn là chuyên gia về danh pháp hóa học quốc tế. Kiểm tra xem '{processed_query}' có tuân theo quy ước đặt tên IUPAC hoặc tên thông thường quốc tế không. Nếu sai, hãy kiểm tra xem có phải là lỗi gần đúng (lỗi chính tả, phiên âm tiếng Việt sai) và đưa ra tên quốc tế đúng. Trả về JSON: {\"is_correct\": true/false, \"corrected_name\": \"<tên đúng>\" hoặc null, \"explanation\": \"<lý do ngắn gọn>\"}."

**Node 4 (generate_response):**
- Input: processed_query (or corrected_name) + rag_context
- Prompt: "Bạn là trợ lý Hóa học lớp 11 thân thiện. Dựa trên truy vấn '{processed_query}' và thông tin sau: '{rag_context}'. Hãy trả lời câu hỏi của học sinh một cách chi tiết. Trả về JSON với các key sau: text_response (câu trả lời đầy đủ bao gồm kết quả kiểm tra tên nếu đã sửa), image_path (lấy từ rag_context.image_path), audio_path (lấy từ rag_context.audio_path). Chỉ sử dụng thông tin trong rag_context; không suy đoán từ kiến thức ngoài. Nếu không đủ thông tin, trả về: {\"text_response\": \"Không đủ thông tin trong CSDL để trả lời.\", \"image_path\": \"\", \"audio_path\": \"\"}."

**TTS Pre-generation (Piper TTS):**
Audio files are generated once using `src/generate_tts.py` before deployment.

Setup:
1. Download Piper voice model from https://github.com/rhasspy/piper/releases
2. Recommended: `en_US-lessac-medium.onnx` (clear American English)
3. Download both `.onnx` and `.json` files
4. Place in `models/` directory
5. Update `PIPER_MODEL_PATH` in `.env`

Generate audio:
```bash
uv run src/generate_tts.py
```

## Scope Coverage (Grade 11 Chemistry - Vietnam)

Compounds to include in data:
- **Alkanes (Ankan):** C1-C6
- **Alkenes (Anken):** C2-C6
- **Alkynes (Ankin):** C2-C6
- **Alcohols (Ancol):** C1-C6
- **Aldehydes (Andehit):** C1-C4
- **Ketones (Xeton):** C3-C6
- **Carboxylic Acids (Axit):** C1-C4
- **Esters (Este):** C1-C4
- **Aromatic:** Benzene, Toluene, Phenol

General documents:
- Naming rules for each class
- Classification overview
- Isomerism basics

## API Keys Required

Store in environment variables (never commit):
- `GOOGLE_GEMINI_API_KEY` - For Gemini 2.5 Flash LLM only
- `PIPER_MODEL_PATH` - Path to downloaded Piper TTS model (.onnx file)
- Qdrant runs locally, no key needed
- Piper TTS runs locally, no API key needed

**Important:** Use `google-genai` package (NOT `google-generativeai`). Import as `from google import genai`.

## Development Workflow

1. **Data Creation:** Manually create JSON files in `data/` following schema
2. **Ingestion:** Run `uv run ingest.py` to populate Qdrant
3. **Backend Development:** Implement LangGraph nodes in sequence
4. **Testing:** Test each node independently with hardcoded inputs
5. **Integration:** Connect nodes in graph, test full workflow
6. **Frontend:** Build Gradio UI to invoke graph (text + image inputs, text + image + audio outputs)
7. **Iteration:** Refine prompts based on edge cases

## Gradio UI Example Structure

```python
import gradio as gr

def process_chemistry_query(text_input, image_input):
    # Invoke LangGraph workflow
    result = graph.invoke({
        "input_text": text_input,
        "input_image": image_input
    })

    return (
        result["final_response"]["text_response"],
        result["final_response"]["image_path"],
        result["final_response"]["audio_url"]
    )

with gr.Blocks() as app:
    gr.Markdown("# Chemistry Chatbot - Lớp 11")

    with gr.Row():
        text_input = gr.Textbox(label="Nhập tên hoặc công thức hóa học")
        image_input = gr.Image(type="filepath", label="Hoặc upload ảnh công thức")

    submit_btn = gr.Button("Tìm kiếm")

    with gr.Row():
        text_output = gr.Markdown(label="Thông tin")
        image_output = gr.Image(label="Cấu trúc phân tử")
        audio_output = gr.Audio(label="Phát âm")

    submit_btn.click(
        process_chemistry_query,
        inputs=[text_input, image_input],
        outputs=[text_output, image_output, audio_output]
    )

app.launch()
```
