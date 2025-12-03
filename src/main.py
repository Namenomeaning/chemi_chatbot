"""FastAPI backend for chemistry chatbot."""

import os
import sys
from pathlib import Path

# Add project root to path for direct script execution
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import base64
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from dotenv import load_dotenv

from src.core.logging import setup_logging
from src.agent.graph import graph
from src.agent.state import AgentState
from src.services import embedding_service

load_dotenv(override=True)
logger = setup_logging(__name__)


# Pydantic Schemas
class QueryRequest(BaseModel):
    """Request schema for chemistry query."""
    text: Optional[str] = Field(default=None, description="Text query")
    image_base64: Optional[str] = Field(default=None, description="Base64-encoded image")
    thread_id: Optional[str] = Field(default=None, description="Thread ID for conversation context")


class QueryResponse(BaseModel):
    """Response schema for chemistry query."""
    success: bool
    thread_id: str
    text_response: Optional[str] = None
    image_path: Optional[str] = None
    audio_path: Optional[str] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Load models
    logger.info("FastAPI startup: Loading embedding model...")
    try:
        embedding_service.load_model()
        logger.info(f"✓ Embedding model loaded (dim: {embedding_service.embedding_dim})")
    except Exception as e:
        logger.error(f"Failed to load embedding model: {str(e)}")
        raise

    yield

    # Shutdown: Cleanup if needed
    logger.info("FastAPI shutdown: Cleaning up...")


# FastAPI app
app = FastAPI(
    title="Chemistry Chatbot API",
    description="LangGraph-powered chemistry chatbot",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"status": "ok", "version": "1.0.0"}


@app.post("/query", response_model=QueryResponse)
async def query_chemistry(request: QueryRequest):
    """Main query endpoint.

    Args:
        request: QueryRequest with text, image_base64, thread_id

    Returns:
        QueryResponse with success, thread_id, text_response, image_path, audio_path, error, metadata
    """
    try:
        # Validate input
        if not request.text and not request.image_base64:
            raise HTTPException(status_code=400, detail="Either text or image_base64 required")

        # Generate thread_id if not provided
        thread_id = request.thread_id or f"thread-{os.urandom(8).hex()}"

        logger.info(f"Query received - thread_id: {thread_id}, has_text: {bool(request.text)}, has_image: {bool(request.image_base64)}")

        # Decode image if provided
        image_bytes = None
        if request.image_base64:
            try:
                image_bytes = base64.b64decode(request.image_base64)
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64: {str(e)}")

        # Prepare state
        initial_state = AgentState(
            input_text=request.text,
            input_image=image_bytes
        )

        # Invoke graph
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(initial_state, config)

        # Check for errors
        error_message = result.get("error_message")
        if error_message:
            logger.warning(f"Query failed - thread_id: {thread_id}, error: {error_message}")
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error=error_message,
                metadata={
                    "rephrased_query": result.get("rephrased_query", ""),
                    "is_chemistry_related": result.get("is_chemistry_related", False),
                    "is_valid": result.get("is_valid", False)
                }
            )

        # Extract response
        final_response = result.get("final_response", {})
        if not final_response:
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error="No response generated"
            )

        logger.info(f"Query succeeded - thread_id: {thread_id}, rag_docs: {len(result.get('rag_context', []))}")

        return QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response=final_response.get("text_response", ""),
            image_path=final_response.get("image_path"),
            audio_path=final_response.get("audio_path"),
            metadata={
                "rephrased_query": result.get("rephrased_query", ""),
                "search_query": result.get("search_query", ""),
                "rag_docs_count": len(result.get("rag_context", []))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query exception - thread_id: {thread_id if 'thread_id' in locals() else 'unknown'}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/query/upload", response_model=QueryResponse)
async def query_with_upload(
    text: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    thread_id: Optional[str] = Form(None)
):
    """Query endpoint with file upload (no base64 needed).

    Args:
        text: Text query
        image: Image file
        thread_id: Thread ID

    Returns:
        QueryResponse
    """
    try:
        # Validate input - check for meaningful text or image
        has_text = text and text.strip()
        has_image = image is not None
        
        if not has_text and not has_image:
            raise HTTPException(status_code=400, detail="Either text or image required")

        # Generate thread_id if not provided
        thread_id = thread_id or f"thread-{os.urandom(8).hex()}"

        # Read image
        image_bytes = None
        if image:
            image_bytes = await image.read()

        # Prepare state
        initial_state = AgentState(
            input_text=text,
            input_image=image_bytes
        )

        # Invoke graph
        config = {"configurable": {"thread_id": thread_id}}
        result = graph.invoke(initial_state, config)

        # Check errors
        error_message = result.get("error_message")
        if error_message:
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error=error_message,
                metadata={
                    "rephrased_query": result.get("rephrased_query", ""),
                    "is_chemistry_related": result.get("is_chemistry_related", False),
                    "is_valid": result.get("is_valid", False)
                }
            )

        # Extract response
        final_response = result.get("final_response", {})
        if not final_response:
            return QueryResponse(
                success=False,
                thread_id=thread_id,
                error="No response generated"
            )

        logger.info(f"Query succeeded - thread_id: {thread_id}, rag_docs: {len(result.get('rag_context', []))}")

        return QueryResponse(
            success=True,
            thread_id=thread_id,
            text_response=final_response.get("text_response", ""),
            image_path=final_response.get("image_path"),
            audio_path=final_response.get("audio_path"),
            metadata={
                "rephrased_query": result.get("rephrased_query", ""),
                "search_query": result.get("search_query", ""),
                "rag_docs_count": len(result.get("rag_context", []))
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query exception - thread_id: {thread_id if 'thread_id' in locals() else 'unknown'}, error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/files/{file_path:path}")
async def serve_file(file_path: str):
    """Serve static files (images, audio).

    Args:
        file_path: Relative path (e.g., "images/ethanol.png" or "data/images/ethanol.png")

    Returns:
        FileResponse
    """
    try:
        # Get project root (parent of src/)
        base_dir = Path(__file__).parent.parent

        # Try with data/ prefix first (current structure)
        full_path = base_dir / "data" / file_path

        # Security check
        if not full_path.resolve().is_relative_to(base_dir.resolve()):
            raise HTTPException(status_code=403, detail="Access denied")

        if not full_path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {file_path}")

        return FileResponse(path=str(full_path))

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
