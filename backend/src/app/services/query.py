import re
import uuid

from app.core.errors import EmptyAgentResponse
from app.schemas.query import QueryRequest, QueryResponse
from app.services.agent import build_agent, read_turn, run_agent
from app.services.audio import load_audio
from app.services.d1_saver import D1Saver
from app.services.quiz import parse_quiz
from app.services.retrieval import ABSTENTION, filter_citations, grounded_context, retrieve
from app.tools.factory import make_tools


async def answer_query(request: QueryRequest, settings, env, principal: str) -> QueryResponse:
    thread_id = request.thread_id or f"thread-{uuid.uuid4().hex}"
    # The same client-visible id cannot read another API key's conversation.
    storage_thread_id = f"{principal}:{thread_id}"
    bucket = getattr(env, "ARTIFACTS", None)
    if request.image_base64:
        content = [
            {"type": "text", "text": request.text or "Đây là hợp chất gì?"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{request.image_base64}"}},
        ]
    else:
        content = request.text

    saver = D1Saver(env.DB)
    prior_messages = []
    if request.thread_id:
        previous = await saver.aget_tuple({"configurable": {"thread_id": storage_thread_id}})
        if previous:
            prior_messages = previous.checkpoint.get("channel_values", {}).get("messages", [])
    question = request.text or ""
    normalized = question.strip().lower()
    if normalized in {"hi", "hello", "xin chào", "chào", "hey"}:
        return QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response="Chào bạn! Mình có thể giúp giải thích hóa học, phát âm tên chất và tạo bài tập.",
        )
    exercise = bool(
        re.search(
            r"quiz|bài tập|luyện tập|trắc nghiệm|tự luận|listening|ghép cặp|câu hỏi|phát âm|pronounce|đọc tên|hình ảnh|ảnh của",
            normalized,
        )
    )
    previous_quiz = any(getattr(m, "name", None) == "generate_quiz" for m in prior_messages[-8:])
    if previous_quiz and len(question) < 160:
        exercise = True
    grounded = settings.rag_enabled and not request.image_base64 and not exercise
    retrieval_query = question
    if len(question) < 100 and re.search(
        r"\b(it|its|that|this|why)\b|của nó|chất đó|công thức|tại sao|gợi ý", normalized
    ):
        previous_questions = [m.content for m in prior_messages if m.type == "human" and isinstance(m.content, str)]
        retrieval_query = " ".join([*previous_questions[-2:], question])
    chunks = []
    messages = []
    if grounded:
        chunks = await retrieve(
            env.DB, getattr(env, "AI", None), getattr(env, "VECTORS", None), settings, retrieval_query
        )
        if not chunks:
            return QueryResponse(success=True, thread_id=thread_id, text_response=ABSTENTION, abstained=True)
    messages.append({"role": "user", "content": content})
    if chunks:
        agent = build_agent(settings, saver, make_tools(settings, bucket), context=grounded_context(chunks))
    else:
        agent = build_agent(settings, saver, make_tools(settings, bucket))
    result = await run_agent(agent, messages, storage_thread_id)
    text, artifacts = read_turn(result["messages"])
    if not text:
        raise EmptyAgentResponse()
    citations = []
    if grounded and not artifacts.get("quiz"):
        text, citations = filter_citations(text, chunks)
        if not citations:
            return QueryResponse(success=True, thread_id=thread_id, text_response=ABSTENTION, abstained=True)
    return QueryResponse(
        success=True,
        thread_id=thread_id,
        text_response=text,
        image_base64=artifacts.get("image", {}).get("url"),
        audio_base64=await load_audio(bucket, artifacts.get("audio", {}).get("key")),
        quiz_data=parse_quiz(artifacts.get("quiz", {}).get("data")),
        citations=citations,
    )
