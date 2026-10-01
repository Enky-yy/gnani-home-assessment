import os
import uuid
import logging
from typing import List, Optional
from datetime import datetime, timezone
from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    UploadFile,
    File,
    Form,
    BackgroundTasks,
    Query,
    status,
)
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, desc

from app.api.deps import get_db, get_storage
from app.config import settings
from app.models.audio_note import AudioNote, ProcessingStatus
from app.schemas.audio_note import (
    AudioNoteResponse,
    AudioNoteListItem,
    AudioNoteStatusResponse,
    AudioNoteUpdateTitle,
)
from app.services.storage import StorageService
from app.services.job_runner import process_audio_note_job
from app.services.queue import enqueue_audio_job
from app.services.summarizer import SummarizerService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "",
    response_model=AudioNoteResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload an audio file and initiate async transcription & summarization",
)
async def upload_audio_note(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Audio recording file (WAV, MP3, M4A, etc.)"),
    title: Optional[str] = Form(None, description="Optional custom title for the note"),
    language_code: str = Form("en-IN", description="BCP-47 language code (e.g. en-IN, hi-IN)"),
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """
    Upload an audio file of any size or duration.
    - Saves audio stream to AWS S3 (or local storage).
    - Enqueues background worker to validate, transcribe with Gnani ASR, and summarize with LLM.
    - Returns 202 Accepted with immediate note metadata.
    """
    filename = os.path.basename(file.filename or "recording.wav")
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported audio format '{ext}'. Allowed formats: {', '.join(settings.ALLOWED_EXTENSIONS)}",
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    declared_size = getattr(file, "size", 0) or 0
    if declared_size > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail=f"File too large ({declared_size / 1024 / 1024:.1f} MB). Limit is {settings.MAX_UPLOAD_SIZE_MB} MB.",
        )

    # Generate persistent unique ID
    note_id = str(uuid.uuid4())
    resolved_title = title.strip() if title and title.strip() else f"Note — {datetime.now().strftime('%b %d, %I:%M %p')}"

    # Determine storage key (partitioned by note_id)
    storage_key = f"audio/{note_id}/{filename}"
    content_type = file.content_type or "audio/wav"

    try:
        # Stream file to storage
        saved_key = storage.upload_file(file.file, storage_key, content_type)
        # Determine actual persisted size (UploadFile.size is not always populated)
        file_size = declared_size
        try:
            file.file.seek(0, os.SEEK_END)
            file_size = file.file.tell()
            file.file.seek(0)
        except Exception:
            pass
        if file_size == 0:
            file_size = declared_size
        if file_size > max_bytes:
            try:
                storage.delete_file(saved_key)
            except Exception:
                pass
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"File too large ({file_size / 1024 / 1024:.1f} MB). Limit is {settings.MAX_UPLOAD_SIZE_MB} MB.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload audio to storage: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Storage upload error: {str(e)}",
        )

    # Generate audio playback URL
    audio_access_url = storage.generate_access_url(saved_key)

    # Create Database Record
    new_note = AudioNote(
        id=note_id,
        title=resolved_title,
        original_filename=filename,
        file_size_bytes=file_size,
        mime_type=content_type,
        storage_backend=settings.STORAGE_BACKEND,
        storage_path=saved_key,
        audio_url=audio_access_url,
        status=ProcessingStatus.UPLOADED,
        progress_percentage=0,
        current_step="Uploaded to storage. Queued for processing.",
        language_code=language_code,
    )

    db.add(new_note)
    await db.commit()
    await db.refresh(new_note)

    # Dispatch background worker: durable Redis queue when available,
    # otherwise in-process BackgroundTasks (zero-infra local dev).
    if not enqueue_audio_job(note_id):
        background_tasks.add_task(process_audio_note_job, note_id)
        logger.info(f"Enqueued in-process background job for note {note_id}")
    else:
        logger.info(f"Enqueued Redis worker job for note {note_id}")

    return new_note


@router.get(
    "",
    response_model=List[AudioNoteListItem],
    summary="List past audio note uploads",
)
async def list_audio_notes(
    q: Optional[str] = Query(None, description="Search query across title, transcript, and filename"),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve history of uploaded notes, ordered chronologically newest first."""
    query = select(AudioNote).order_by(desc(AudioNote.created_at))

    if q and q.strip():
        search_filter = f"%{q.strip()}%"
        query = query.where(
            or_(
                AudioNote.title.ilike(search_filter),
                AudioNote.original_filename.ilike(search_filter),
                AudioNote.raw_transcript.ilike(search_filter),
                AudioNote.summary_tldr.ilike(search_filter),
            )
        )

    query = query.offset(offset).limit(limit)
    result = await db.execute(query)
    notes = result.scalars().all()
    return notes


@router.get(
    "/{note_id}",
    response_model=AudioNoteResponse,
    summary="Get full note details, transcript, and AI summary",
)
async def get_audio_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """Retrieve full details for an audio note including timestamped segments."""
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio note '{note_id}' not found.",
        )

    # Ensure audio URL is fresh (e.g. presigned S3 expiry refresh)
    if note.storage_path and settings.STORAGE_BACKEND.lower() == "s3":
        note.audio_url = storage.generate_access_url(note.storage_path)

    return note


@router.get(
    "/{note_id}/status",
    response_model=AudioNoteStatusResponse,
    summary="Fast polling endpoint for real-time progress tracking",
)
async def get_audio_note_status(
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Lightweight endpoint used by frontend to poll processing status and percent without heavy transcript payload."""
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio note '{note_id}' not found.",
        )

    return note


@router.get(
    "/{note_id}/audio",
    summary="Stream raw audio file or redirect to S3 presigned URL",
)
async def stream_audio_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    """Stream audio content for browser HTML5 audio element."""
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio note not found.")

    if settings.STORAGE_BACKEND.lower() == "s3":
        presigned_url = storage.generate_access_url(note.storage_path)
        return RedirectResponse(url=presigned_url)

    # For local storage, stream local file with range header support
    local_path = None
    if hasattr(storage, "resolve_local_path"):
        try:
            local_path = storage.resolve_local_path(note.storage_path)
        except ValueError as e:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    else:
        local_path = os.path.join(settings.LOCAL_STORAGE_DIR, os.path.basename(note.storage_path))
    if not local_path or not os.path.exists(local_path):
        # Legacy fallback: files saved by the old basename-only layout
        legacy = os.path.join(
            os.path.abspath(settings.LOCAL_STORAGE_DIR), os.path.basename(note.storage_path)
        )
        if os.path.exists(legacy):
            local_path = legacy
        else:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio file missing on disk.")

    return FileResponse(
        local_path,
        media_type=note.mime_type or "audio/mpeg",
        filename=note.original_filename,
    )


@router.post(
    "/{note_id}/retry",
    response_model=AudioNoteResponse,
    summary="Retry a failed or incomplete audio note",
)
async def retry_audio_note(
    note_id: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Reset a failed note and re-enqueue background worker."""
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio note not found.")

    note.status = ProcessingStatus.UPLOADED
    note.progress_percentage = 0
    note.current_step = "Retrying processing..."
    note.error_message = None
    note.retry_count += 1
    note.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(note)

    if not enqueue_audio_job(note_id):
        background_tasks.add_task(process_audio_note_job, note_id)
        logger.info(f"Re-enqueued in-process processing for note {note_id} (retry #{note.retry_count})")
    else:
        logger.info(f"Re-enqueued Redis processing for note {note_id} (retry #{note.retry_count})")

    return note


@router.post(
    "/{note_id}/summarize",
    response_model=AudioNoteResponse,
    summary="Re-run LLM summarization on the existing transcript",
)
async def resummarize_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Re-summarize without re-transcribing (e.g. after swapping LLM keys).

    Uses the stored raw transcript only — no Gnani call, no audio needed.
    """
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio note not found.")

    if not note.raw_transcript or not note.raw_transcript.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No transcript to summarize yet. Transcribe the note first.",
        )

    try:
        summary_data = await SummarizerService().summarize(note.raw_transcript)
    except Exception as e:
        logger.error(f"Summarization failed for note {note_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Summarization failed: {str(e)}",
        )

    note.summary_tldr = summary_data.get("tldr")
    note.summary_key_points = summary_data.get("key_points", [])
    note.summary_action_items = summary_data.get("action_items", [])
    note.summary_sentiment = summary_data.get("sentiment", "Neutral")
    note.llm_model_used = summary_data.get("model_used", "unknown")
    note.updated_at = datetime.now(timezone.utc)

    await db.commit()
    await db.refresh(note)
    logger.info(f"Re-summarized note {note_id} with {note.llm_model_used}")
    return note


@router.patch(
    "/{note_id}/title",
    response_model=AudioNoteResponse,
    summary="Update audio note title",
)
async def update_note_title(
    note_id: str,
    payload: AudioNoteUpdateTitle,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio note not found.")

    note.title = payload.title.strip()
    note.updated_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(note)
    return note


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete audio note and purge storage",
)
async def delete_audio_note(
    note_id: str,
    db: AsyncSession = Depends(get_db),
    storage: StorageService = Depends(get_storage),
):
    result = await db.execute(select(AudioNote).where(AudioNote.id == note_id))
    note = result.scalar_one_or_none()

    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Audio note not found.")

    # Remove file from storage
    if note.storage_path:
        try:
            storage.delete_file(note.storage_path)
        except Exception as e:
            logger.warning(f"Could not delete storage file {note.storage_path}: {e}")

    await db.delete(note)
    await db.commit()
    return None
