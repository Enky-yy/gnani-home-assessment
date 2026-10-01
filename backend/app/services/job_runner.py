import os
import tempfile
import logging
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.audio_note import AudioNote, ProcessingStatus
from app.services.storage import get_storage_service
from app.services.audio import AudioService, AudioProcessingError
from app.services.gnani_stt import GnaniSTTClient, GnaniSTTError
from app.services.summarizer import SummarizerService

logger = logging.getLogger(__name__)


async def update_note_progress(
    note_id: str,
    status: ProcessingStatus,
    progress: int,
    step_description: str,
    error_message: str = None,
    duration: float = None,
):
    """Helper to update a note's processing state atomically."""
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudioNote).where(AudioNote.id == note_id))
        note = result.scalar_one_or_none()
        if not note:
            logger.error(f"Cannot update progress: Note {note_id} not found in database.")
            return

        note.status = status
        note.progress_percentage = progress
        note.current_step = step_description
        if error_message:
            note.error_message = error_message
        if duration is not None:
            note.duration_seconds = duration
        note.updated_at = datetime.now(timezone.utc)

        await session.commit()
        logger.info(f"Note {note_id} state updated -> {status.value} ({progress}%): {step_description}")


async def process_audio_note_job(note_id: str) -> None:
    """
    Main asynchronous background worker pipeline for processing an uploaded audio note:
    1. Download audio file from storage (AWS S3 or Local) to local worker scratch directory.
    2. Validate and inspect audio format using FFmpeg/ffprobe.
    3. Transcribe audio with Gnani Voice AI (Single REST if <= GNANI_MAX_REST_AUDIO_SECONDS,
       or chunked with overlap if longer).
    4. Generate structured summary, TL;DR, and action items via LLM.
    5. Persist transcripts, segments, and summary to PostgreSQL.
    6. Gracefully handle and record any failures visibly.
    """
    logger.info(f"Starting background job for audio note: {note_id}")
    storage_svc = get_storage_service()
    gnani_client = GnaniSTTClient()
    summarizer_svc = SummarizerService()

    # 1. Fetch initial note record
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudioNote).where(AudioNote.id == note_id))
        note = result.scalar_one_or_none()
        if not note:
            logger.error(f"Job aborted: Note {note_id} does not exist.")
            return
        
        storage_path = note.storage_path
        language_code = note.language_code
        original_filename = note.original_filename

    # Create temporary scratch directory
    temp_dir = tempfile.mkdtemp(prefix=f"note_{note_id[:8]}_")
    local_audio_path = os.path.join(temp_dir, os.path.basename(original_filename))

    try:
        # Step 1: Preprocessing & Downloading (0 -> 20%)
        await update_note_progress(
            note_id,
            ProcessingStatus.PREPROCESSING,
            10,
            "Retrieving audio from secure storage...",
        )

        storage_svc.download_file(storage_path, local_audio_path)

        await update_note_progress(
            note_id,
            ProcessingStatus.PREPROCESSING,
            18,
            "Validating audio stream & inspecting codecs with FFmpeg...",
        )

        metadata = AudioService.inspect_audio(local_audio_path)
        duration_sec = metadata.duration_seconds
        logger.info(
            f"Note {note_id} validated: duration={duration_sec:.2f}s, format={metadata.format_name}, sample_rate={metadata.sample_rate}"
        )

        # Step 2: Transcribing with Gnani Voice AI (20 -> 75%)
        await update_note_progress(
            note_id,
            ProcessingStatus.TRANSCRIBING,
            25,
            f"Dispatching to Gnani Voice AI ({duration_sec:.1f}s audio)...",
            duration=duration_sec,
        )

        async def gnani_progress_callback(pct: int, msg: str):
            await update_note_progress(
                note_id,
                ProcessingStatus.TRANSCRIBING,
                pct,
                msg,
                duration=duration_sec,
            )

        transcription_res = await gnani_client.transcribe(
            file_path=local_audio_path,
            duration_seconds=duration_sec,
            language_code=language_code,
            scratch_dir=os.path.join(temp_dir, "chunks"),
            progress_callback=gnani_progress_callback,
        )

        if not transcription_res.raw_transcript or not transcription_res.raw_transcript.strip():
            logger.warning(f"Note {note_id} produced empty transcript.")
            transcription_res.raw_transcript = "[No intelligible speech detected in this audio recording]"

        # Step 3: Summarizing with LLM (75 -> 95%)
        await update_note_progress(
            note_id,
            ProcessingStatus.SUMMARIZING,
            80,
            "Synthesizing key insights & action items with AI...",
            duration=duration_sec,
        )

        summary_data = await summarizer_svc.summarize(transcription_res.raw_transcript)

        # Step 4: Persist final results to PostgreSQL (100% - COMPLETED)
        async with AsyncSessionLocal() as session:
            result = await session.execute(select(AudioNote).where(AudioNote.id == note_id))
            note = result.scalar_one_or_none()
            if note:
                note.status = ProcessingStatus.COMPLETED
                note.progress_percentage = 100
                note.current_step = "Processing completed successfully"
                note.error_message = None  # Clear any previous retry errors
                note.duration_seconds = duration_sec
                note.asr_engine_used = transcription_res.engine_used
                note.gnani_job_id = transcription_res.job_id
                note.raw_transcript = transcription_res.raw_transcript
                note.transcript_segments = transcription_res.segments
                note.summary_tldr = summary_data.get("tldr")
                note.summary_key_points = summary_data.get("key_points", [])
                note.summary_action_items = summary_data.get("action_items", [])
                note.summary_sentiment = summary_data.get("sentiment", "Neutral")
                note.llm_model_used = summary_data.get("model_used", "gemini")
                note.updated_at = datetime.now(timezone.utc)
                await session.commit()

        logger.info(f"Note {note_id} successfully processed and marked COMPLETED.")

    except AudioProcessingError as ape:
        err_msg = f"Audio validation failed: {str(ape)}"
        logger.error(f"Job failed for {note_id}: {err_msg}")
        await update_note_progress(note_id, ProcessingStatus.FAILED, 100, "Audio file rejected", error_message=err_msg)

    except GnaniSTTError as gse:
        err_msg = f"Gnani ASR error: {str(gse)}"
        logger.error(f"Job failed for {note_id}: {err_msg}")
        await update_note_progress(note_id, ProcessingStatus.FAILED, 100, "Transcription failed", error_message=err_msg)

    except Exception as e:
        err_msg = f"Unexpected processing error: {str(e)}"
        logger.exception(f"Job failed with unexpected error for {note_id}: {err_msg}")
        await update_note_progress(note_id, ProcessingStatus.FAILED, 100, "Processing error", error_message=err_msg)

    finally:
        # Clean up scratch files
        try:
            if os.path.exists(temp_dir):
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
        except Exception:
            pass
