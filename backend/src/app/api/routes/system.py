from fastapi import APIRouter, Depends, HTTPException

from app.api.deps import get_env

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "service": "CHEMI Chemistry Chatbot"}


@router.get("/ready")
async def ready(env=Depends(get_env)):
    try:
        await env.DB.prepare("SELECT 1 AS ok").first()
    except Exception as e:
        raise HTTPException(503, f"database not ready: {type(e).__name__}") from e
    return {"status": "ready"}
