import os
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.api.deps import get_db, get_storage
from app.config import settings, is_configured_key
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
            base_dir = settings.LOCAL_STORAGE_DIR
            writable = os.access(base_dir, os.W_OK) if os.path.exists(base_dir) else False
            # Ensure the directory exists (LocalStorageService also creates it on init)
            if not os.path.exists(base_dir):
                os.makedirs(base_dir, exist_ok=True)
                writable = True
            storage_status = (
                f"local-storage-ready ({base_dir})" if writable else f"local-storage-not-writable ({base_dir})"
            )
    except Exception as e:
        storage_status = f"unhealthy: {str(e)}"

    # Check job queue (Redis when configured)
    queue_info: dict = {"backend": "background-tasks"}
    try:
        from app.services.queue import get_queue_depth, is_redis_available

        if (settings.REDIS_URL or "").strip():
            if is_redis_available():
                queue_info = {
                    "backend": "redis",
                    "queue": settings.JOB_QUEUE_NAME,
                    "pending_jobs": get_queue_depth(),
                    "status": "connected",
                }
            else:
                queue_info = {"backend": "redis", "status": "unreachable (fallback: background-tasks)"}
    except Exception as e:
        queue_info = {"backend": "background-tasks", "status": f"queue check failed: {e}"}

    # Check Gnani configuration
    has_gnani_key = bool(settings.GNANI_API_KEY and settings.GNANI_API_KEY.strip())
    gnani_status = "active" if has_gnani_key else "demo-simulation-mode (no GNANI_API_KEY)"

    # Check LLM configuration
    has_llm_key = any(is_configured_key(k) for k in (settings.GEMINI_API_KEY, settings.GROQ_API_KEY, settings.OPENAI_API_KEY))
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
        "queue": queue_info,
        "integrations": {
            "gnani_asr": gnani_status,
            "llm_summarizer": llm_status,
        }
    }
