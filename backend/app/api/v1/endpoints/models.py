import time
from fastapi import APIRouter
from app.config import settings

router = APIRouter()


@router.get("", summary="List available models (OpenAI-compatible)")
async def list_models():
    """Return available LLM summarization and Gnani ASR speech recognition models."""
    now = int(time.time())

    models = [
        {
            "id": settings.GEMINI_MODEL,
            "object": "model",
            "created": now,
            "owned_by": "google",
            "type": "llm",
            "active": settings.LLM_PROVIDER == "gemini",
        },
        {
            "id": settings.GROQ_MODEL,
            "object": "model",
            "created": now,
            "owned_by": "groq",
            "type": "llm",
            "active": settings.LLM_PROVIDER == "groq",
        },
        {
            "id": settings.OPENAI_MODEL,
            "object": "model",
            "created": now,
            "owned_by": "openai",
            "type": "llm",
            "active": settings.LLM_PROVIDER == "openai",
        },
        {
            "id": "gnani-prisma-v2.5",
            "object": "model",
            "created": now,
            "owned_by": "gnani",
            "type": "asr",
            "active": True,
        },
    ]

    return {
        "object": "list",
        "data": models,
        "active_llm_provider": settings.LLM_PROVIDER,
    }
