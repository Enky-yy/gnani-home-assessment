import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # App General
    PROJECT_NAME: str = "Audio Notes Platform API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = False

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://127.0.0.1:3000", "*"]

    # Database
    # Default to PostgreSQL, with automatic fallback for SQLite when DATABASE_URL is not set or in local testing
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/audio_notes"
    DB_ECHO: bool = False

    # Storage Settings
    # Options: "s3" or "local"
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_DIR: str = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "uploads"))
    
    # AWS S3 Settings
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-south-1"
    AWS_S3_BUCKET_NAME: str = "audio-notes-platform"
    AWS_S3_ENDPOINT_URL: Optional[str] = None  # For LocalStack or MinIO if needed
    S3_PRESIGNED_EXPIRY_SECONDS: int = 3600

    # Gnani STT API Settings
    GNANI_API_KEY: Optional[str] = None
    GNANI_BASE_URL: str = "https://api.vachana.ai"
    GNANI_REST_ENDPOINT: str = "https://api.vachana.ai/stt/v3"
    GNANI_BATCH_JOBS_ENDPOINT: str = "https://api.vachana.ai/stt/v3/batch/jobs"
    GNANI_DEFAULT_LANGUAGE: str = "en-IN"
    GNANI_MAX_REST_AUDIO_SECONDS: int = 25  # Gnani REST STT hard cap is 30s; chunk anything > 25s

    # LLM Summarization Settings
    # Options: "gemini", "groq", "openai"
    LLM_PROVIDER: str = "gemini"
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-flash-latest"
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Upload Constraints (500MB ≈ 8+ hours of MP3 / 4+ hours of WAV —
    # effectively any recording a user would upload, while still bounding disk abuse)
    MAX_UPLOAD_SIZE_MB: int = 500
    ALLOWED_EXTENSIONS: List[str] = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm"]

    # Background job queue (Redis). Empty/disabled -> in-process BackgroundTasks fallback.
    REDIS_URL: Optional[str] = None
    JOB_QUEUE_NAME: str = "audio_notes:jobs"

    model_config = SettingsConfigDict(
        env_file=(
            os.path.join(os.path.dirname(__file__), "..", ".env"),
            os.path.join(os.path.dirname(__file__), "..", "..", ".env"),
            ".env",
        ),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()


def is_configured_key(value: Optional[str]) -> bool:
    """True only for a real key — ignores empty values and .env.example
    placeholders like 'your_groq_api_key_here' so they are never treated
    as configured or sent to provider APIs (which just 401)."""
    v = (value or "").strip().strip("\"'")
    if not v:
        return False
    lowered = v.lower()
    return not (
        lowered.startswith("your_")
        or lowered.endswith("_here")
        or "example" in lowered
        or "placeholder" in lowered
        or "changeme" in lowered
    )
