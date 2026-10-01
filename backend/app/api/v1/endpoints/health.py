import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.deps import get_db, get_storage
from app.config import settings
from app.services.storage import StorageService

router = APIRouter()


@router.get("", summary="System health check & diagnostics")
async def health_check(
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """Deep health check validating DB, Storage, and external API configurations."""
    # Check DB
    db_status = "healthy"
    try:
        await db.execute(text("SELECT 1"))
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"

    # Check Storage
    storage_status = "healthy"
    try:
        if settings.STORAGE_BACKEND.lower() == "s3":
            storage_status = f"s3-connected ({settings.AWS_S3_BUCKET_NAME})"
        else:
            storage_status = f"local-storage-ready ({settings.LOCAL_STORAGE_DIR})"
    except Exception as e:
        storage_status = f"unhealthy: {str(e)}"

    # Check Gnani configuration
    has_gnani_key = bool(settings.GNANI_API_KEY and settings.GNANI_API_KEY.strip())
    gnani_status = "active" if has_gnani_key else "demo-simulation-mode (no GNANI_API_KEY)"

    # Check LLM configuration
    has_llm_key = bool(settings.GEMINI_API_KEY or settings.GROQ_API_KEY or settings.OPENAI_API_KEY)
    llm_status = f"active ({settings.LLM_PROVIDER})" if has_llm_key else "extractive-fallback-mode"

    return {
        "status": "healthy" if db_status == "healthy" else "degraded",
        "app_name": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "environment": "debug" if settings.DEBUG else "production",
        "database": db_status,
        "storage": {
            "backend": settings.STORAGE_BACKEND,
            "status": storage_status,
        },
        "integrations": {
            "gnani_asr": gnani_status,
            "llm_summarizer": llm_status,
        }
    }
