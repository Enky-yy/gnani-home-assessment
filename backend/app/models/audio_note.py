import uuid
from datetime import datetime, timezone
import enum
from sqlalchemy import (
    Column,
    String,
    BigInteger,
    Float,
    Integer,
    Text,
    DateTime,
    JSON,
    Enum as SQLEnum,
)
from app.database import Base


class ProcessingStatus(str, enum.Enum):
    UPLOADED = "UPLOADED"
    PREPROCESSING = "PREPROCESSING"
    TRANSCRIBING = "TRANSCRIBING"
    SUMMARIZING = "SUMMARIZING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AudioNote(Base):
    __tablename__ = "audio_notes"

    # Identity
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()), index=True)
    title = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)
    duration_seconds = Column(Float, nullable=True)

    # Storage
    storage_backend = Column(String(50), nullable=False, default="s3")
    storage_path = Column(String(500), nullable=False)
    audio_url = Column(Text, nullable=True)

    # Execution State
    status = Column(
        SQLEnum(ProcessingStatus, native_enum=False, length=50),
        nullable=False,
        default=ProcessingStatus.UPLOADED,
        index=True,
    )
    progress_percentage = Column(Integer, nullable=False, default=0)
    current_step = Column(String(255), nullable=False, default="File uploaded")
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, nullable=False, default=0)

    # Transcription details
    language_code = Column(String(20), nullable=False, default="en-IN")
    asr_engine_used = Column(String(50), nullable=True)
    gnani_job_id = Column(String(100), nullable=True)
    raw_transcript = Column(Text, nullable=True)
    transcript_segments = Column(JSON, nullable=True)  # List of {start: float, end: float, text: str}

    # Summary details
    summary_tldr = Column(Text, nullable=True)
    summary_key_points = Column(JSON, nullable=True)  # List of strings
    summary_action_items = Column(JSON, nullable=True)  # List of strings
    summary_sentiment = Column(String(50), nullable=True)
    llm_model_used = Column(String(100), nullable=True)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "original_filename": self.original_filename,
            "file_size_bytes": self.file_size_bytes,
            "mime_type": self.mime_type,
            "duration_seconds": self.duration_seconds,
            "storage_backend": self.storage_backend,
            "storage_path": self.storage_path,
            "audio_url": self.audio_url,
            "status": self.status.value if isinstance(self.status, ProcessingStatus) else str(self.status),
            "progress_percentage": self.progress_percentage,
            "current_step": self.current_step,
            "error_message": self.error_message,
            "retry_count": self.retry_count,
            "language_code": self.language_code,
            "asr_engine_used": self.asr_engine_used,
            "gnani_job_id": self.gnani_job_id,
            "raw_transcript": self.raw_transcript,
            "transcript_segments": self.transcript_segments or [],
            "summary_tldr": self.summary_tldr,
            "summary_key_points": self.summary_key_points or [],
            "summary_action_items": self.summary_action_items or [],
            "summary_sentiment": self.summary_sentiment,
            "llm_model_used": self.llm_model_used,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
