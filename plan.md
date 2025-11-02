AI AGENT ĐỌC TÊN ĐỌC PHÁP DANH CHO CÔNG THỨC HÓA HỌC LỚP 11 

👑 Giai đoạn 1: Xây dựng Nền tảng Tri thức (RAG)
Đây là bước quan trọng nhất. Agent của bạn chỉ có thể trả lời đúng những gì nó "biết". Bạn cần "số hóa" toàn bộ kiến thức trong ảnh và mở rộng nó.

1.1. Thiết kế Cấu trúc Dữ liệu (Data Schema): Tạo một thư mục chứa các file (ví dụ: .json) cho mỗi hợp chất hoặc nhóm hợp chất. Mỗi file là một "tài liệu" (document) trong RAG.

Cấu trúc file ethanol.json (ví dụ, đã mở rộng schema tối thiểu để dễ truy vấn và hiển thị):

JSON

{
  "doc_id": "ethanol",
  "class": "alcohol",
  "subclass": "primary",
  "names": {
    "iupac_en": "Ethanol",
    "common_vi": ["Rượu etylic", "Ancol etylic", "Cồn"],
    "common_en": ["ethyl alcohol", "alcohol"]
  },
  "formulas": {
    "molecular": "C2H6O",
    "condensed": ["C2H5OH", "CH3-CH2-OH"],
    "smiles": "CCO"
  },
  "urls": {
    "structure_svg": "<https://upload.wikimedia.org/wikipedia/commons/3/3c/Ethanol-structure.svg>"
  },
  "info": "Ethanol là một ancol đơn chức bậc 1, chất lỏng không màu, tan vô hạn trong nước. Là thành phần chính của đồ uống có cồn...",
  "examples_naming": [
    "Tên hydrocarbon tương ứng (ethane) + hậu tố '-ol' → ethanol"
  ],
  "tags": ["C1-C2", "alcohol", "primary"],
  "aliases_normalized": ["ethanol", "ruou etylic", "ancol etylic", "con", "c2h5oh", "ch3ch2oh"],
  "doc_text": "Ethanol ethyl alcohol rượu etylic ancol etylic C2H5OH CH3CH2OH ancol đơn chức bậc 1..."
}
1.2. Tạo Dữ liệu:

Hợp chất: Tạo các file JSON cho tất cả các chất trong danh sách của bạn (Ankan, Anken, Ankin, Ancol C1-C6, Este C1-C4, v.v.).

Tài liệu chung: Tạo các file cho các câu hỏi tổng quan, ví dụ rules_alkane.json (Quy tắc gọi tên Ankan), classification.json (Tổng quan phân loại hợp chất hữu cơ).

1.3. Thiết lập Vector Database:

Công cụ: Qdrant 3.x (chạy local bằng Docker hoặc binary; miễn phí, dễ cài đặt).

Mô hình Embedding: Qwen/Qwen3-Embedding-0.6B (đa ngôn ngữ, hiệu quả cho VI/EN).

Quy trình (Ingestion): Viết một script (ingest.py) để:

Đọc tất cả các file .json.

Kết hợp các trường văn bản quan trọng (như iupac_name, common_name, formula, search_keywords, info) thành một chuỗi văn bản duy nhất cho mỗi tài liệu.

Vector hóa chuỗi này bằng mô hình embedding.

Lưu vector và doc_id cùng toàn bộ file JSON làm payload vào Qdrant (mỗi document là một "point" trong một "collection").

🌀 Giai đoạn 2: Thiết kế Kiến trúc Luồng (LangGraph)
Đây là bộ não điều phối của Agent. Chúng ta sẽ sử dụng kiến trúc tuần tự đơn giản, tận dụng sức mạnh của Gemini.

2.1. Định nghĩa Trạng thái (State): Đây là "bộ nhớ" luân chuyển qua các node.

Python

from typing import TypedDict, List, Optional

class AgentState(TypedDict):
    input_text: Optional[str]      # Văn bản gốc từ user
    input_image: Optional[bytes]   # Ảnh gốc từ user
    processed_query: str           # Tên/công thức đã được Gemini trích xuất
    rag_context: List[dict]        # Danh sách các tài liệu (JSON) lấy từ RAG
    final_response: dict           # Output JSON cuối cùng (chứa text, link ảnh, link audio)
2.2. Định nghĩa các Node (Các bước xử lý):

Node 1: extract_chemical_query (Trích xuất truy vấn)

Input: state['input_text'], state['input_image']

Công cụ: Gemini 2.5 Flash 

Prompt (Rất quan trọng):

"Bạn là chuyên gia hóa học. Phân tích văn bản và/hoặc hình ảnh được cung cấp. Nhiệm vụ của bạn là xác định chính xác tên (IUPAC, thông thường) hoặc công thức hóa học (CTPT, CTCT) mà người dùng đang hỏi. Ví dụ:

Input: ảnh CH3COOH, text "đây là gì?" -> Output: "Acetic Acid"

Input: "quy tắc gọi tên ankan" -> Output: "Quy tắc gọi tên Ankan"

Chỉ trả về chuỗi text duy nhất là tên hoặc công thức đó."

Output: Cập nhật state['processed_query'] (ví dụ: "Ethanol").

Node 2: retrieve_from_rag (Truy xuất RAG)

Input: state['processed_query']

Công cụ: Vector Database (ChromaDB/FAISS) đã tạo ở Giai đoạn 1.

Logic:

Embed processed_query.

Tìm kiếm K tài liệu tương đồng nhất (K=3).

Output: Cập nhật state['rag_context'] với danh sách các JSON tìm được.

Node 3: generate_response (Tổng hợp câu trả lời)

Input: state['processed_query'], state['rag_context']

Công cụ: LLM (Gemini)

Prompt:

"Bạn là trợ lý Hóa học lớp 11 thân thiện. Dựa trên truy vấn '{processed_query}' và thông tin sau: '{rag_context}'. Hãy trả lời câu hỏi của học sinh một cách chi tiết. Sau đó, hãy trả về một JSON object với 3 key sau:

text_response: Câu trả lời đầy đủ (giới thiệu, phân loại, quy tắc gọi tên, thông tin thêm...).

tts_input_name: Tên IUPAC tiếng Anh chính xác của hợp chất (trích từ context).

structure_image_url: Đường link ảnh cấu trúc (trích từ structure_image_url trong context).

"Nếu không tìm thấy thông tin, hãy thông báo."

Yêu cầu bổ sung:

- Chỉ sử dụng thông tin trong rag_context; không suy đoán từ kiến thức ngoài.
- Nếu thông tin không đủ, trả về JSON hợp lệ với:
  { "text_response": "Không đủ thông tin trong CSDL để trả lời.", "tts_input_name": "", "structure_image_url": "" }
- Trả về duy nhất một JSON hợp lệ.

Output: Phân tích JSON từ LLM, validate theo schema và cập nhật state['final_response'] (chỉ chứa text_response, tts_input_name, structure_image_url). Nếu JSON không hợp lệ, thực hiện một lần yêu cầu lại với nhắc nhở "chỉ trả về JSON hợp lệ".

Node 4: generate_audio (Tạo âm thanh)

Input: `state['final_response']['tts_input_name']` (ví dụ: "Ethanol")

Công cụ: Google Cloud TTS API / OpenAI TTS API

Logic:

Gọi API TTS với text là tts_input_name.

Quan trọng: Đặt ngôn ngữ/giọng đọc là en-US hoặc en-GB để đảm bảo phát âm chuẩn tiếng Anh.

Lưu file audio (ví dụ: output.mp3) và tạo một URL/đường dẫn có thể truy cập được.

Output: Thêm key audio_url vào state['final_response'].

2.3. Liên kết các Node (Graph Edges): Đây là một luồng tuần tự đơn giản.

START -> extract_chemical_query

extract_chemical_query -> retrieve_from_rag

retrieve_from_rag -> generate_response

generate_response -> generate_audio

generate_audio -> END

⚙️ Giai đoạn 3: Công cụ & Ngăn xếp Công nghệ (Tech Stack)
Ngôn ngữ: Python 3.10+

Orchestration: langgraph

Mô hình LLM/VQA: Google Gemini 2.5 Flash

Mô hình Embedding: Qwen/Qwen3-Embedding-0.6B (chạy local qua Transformers/sentence-transformers)

Vector Database: Qdrant (chạy local)

Text-to-Speech: google-cloud-tts hoặc openai (qua API)

API Backend: fastapi (để nhận request từ frontend)

Frontend (Prototyping): streamlit (cách nhanh nhất để có giao diện cho phép upload ảnh và nhập text).

🏃 Giai đoạn 4: Lộ trình Thực thi (Workflow)
Tuần 1: Data Foundation

[ ] Cài đặt môi trường Python (venv).

[ ] Khởi chạy Qdrant (Docker hoặc binary local).

[ ] Hoàn thiện schema.json.

[ ] Tạo thủ công các file JSON mẫu cho các hợp chất quan trọng (ví dụ: Methane, Ethene, Ethyne, Ethanol, Acetic Acid, Ethyl Acetate...).

[ ] Viết và chạy script ingest.py để nạp các file này vào Qdrant.

Tuần 2: Core Logic (LangGraph)

[ ] Viết mã cho 4 node (extract..., retrieve..., generate..., generate...).

[ ] Lấy API key cho Gemini và TTS.

[ ] Định nghĩa AgentState và kết nối các node trong LangGraph.

[ ] Test trong terminal: Chạy file Python với input cứng (hard-coded) để kiểm tra toàn bộ luồng.

Tuần 3: Giao diện (Frontend)

[ ] Dựng một app Streamlit đơn giản.

[ ] Tạo 1 ô nhập text (st.text_input).

[ ] Tạo 1 ô upload ảnh (st.file_uploader).

[ ] Tạo 1 nút "Gửi" (st.button).

[ ] Khi nhấn nút, gọi hàm graph.invoke(...) của LangGraph.

[ ] Hiển thị 3 output:

st.markdown(response['text_response'])

st.image(response['structure_image_url'])

st.audio(response['audio_url'])

Tuần 4: Mở rộng & Hoàn thiện

[ ] (Song song) Hoàn thiện nốt dữ liệu RAG cho toàn bộ danh sách lớp 11.

[ ] Chạy lại ingest.py để nạp toàn bộ dữ liệu.

[ ] Tinh chỉnh prompt (đặc biệt là node_extract_query và node_generate_response) để xử lý các trường hợp ngoại lệ (ví dụ: không tìm thấy chất).

🧪 Giai đoạn 5: Kiểm thử (Testing)
Test đa phương thức: "Đây là chất gì?" + ảnh CH3COOH.

Test chỉ text: "Ethanoic acid là gì?", "CTCT của propan-1-ol".

Test chỉ ảnh: Upload ảnh cấu trúc của "Benzene" (dù ngoài danh sách) xem nó phản ứng ra sao.

Test tổng quan: "Quy tắc gọi tên este là gì?".

Test phát âm: Đảm bảo file audio đọc "Ethanol" (tiếng Anh) chứ không phải "E-tha-non" (tiếng Việt).

Kế hoạch này cung cấp một lộ trình rõ ràng, bắt đầu từ nền tảng dữ liệu và xây dựng dần lên một agent hoàn chỉnh, thông minh.
