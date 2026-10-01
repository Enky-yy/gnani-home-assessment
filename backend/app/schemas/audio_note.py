from typing import List, Optional, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict
from app.models.audio_note import ProcessingStatus


class TranscriptSegment(BaseModel):
    start: float = Field(..., description="Start time in seconds")
    end: float = Field(..., description="End time in seconds")
    text: str = Field(..., description="Transcribed text segment")
    speaker: Optional[str] = Field(None, description="Speaker identifier if diarized")


class SummaryData(BaseModel):
    tldr: Optional[str] = Field(None, description="Executive 2-3 sentence overview")
    key_points: List[str] = Field(default_factory=list, description="Key discussion takeaways")
    action_items: List[str] = Field(default_factory=list, description="Tasks and follow-ups")
    sentiment: Optional[str] = Field(None, description="General tone and sentiment")


class AudioNoteBase(BaseModel):
    title: str
    language_code: str = "en-IN"


class AudioNoteCreate(AudioNoteBase):
    original_filename: str
    file_size_bytes: int
    mime_type: str
    storage_path: str
    storage_backend: str = "s3"


class AudioNoteStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    status: ProcessingStatus
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None
    retry_count: int
    duration_seconds: Optional[float] = None
    updated_at: Optional[datetime] = None


class AudioNoteListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    file_size_bytes: int
    duration_seconds: Optional[float] = None
    status: ProcessingStatus
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None
    summary_tldr: Optional[str] = None
    summary_sentiment: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AudioNoteResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    original_filename: str
    file_size_bytes: int
    mime_type: str
    duration_seconds: Optional[float] = None
    storage_backend: str
    storage_path: str
    audio_url: Optional[str] = None
    status: ProcessingStatus
    progress_percentage: int
    current_step: str
    error_message: Optional[str] = None
    retry_count: int
    language_code: str
    asr_engine_used: Optional[str] = None
    gnani_job_id: Optional[str] = None
    raw_transcript: Optional[str] = None
    transcript_segments: Optional[List[TranscriptSegment]] = Field(default_factory=list)
    summary_tldr: Optional[str] = None
    summary_key_points: Optional[List[str]] = Field(default_factory=list)
    summary_action_items: Optional[List[str]] = Field(default_factory=list)
    summary_sentiment: Optional[str] = None
    llm_model_used: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class AudioNoteUpdateTitle(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)
