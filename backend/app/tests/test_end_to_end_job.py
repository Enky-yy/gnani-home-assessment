import os
import math
import struct
import wave
import tempfile
import pytest
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.audio_note import AudioNote, ProcessingStatus
from app.services.storage import get_storage_service
from app.services.job_runner import process_audio_note_job


def generate_long_wav(file_path: str, duration_sec: float = 70.0, sample_rate: int = 16000):
    """Generate audio longer than 60s to trigger chunking engine."""
    num_samples = int(duration_sec * sample_rate)
    with wave.open(file_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        # Write silence or small tone blocks
        chunk_size = 16000
        tone_block = bytearray()
        for i in range(chunk_size):
            val = int(32767.0 * 0.2 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            tone_block.extend(struct.pack("<h", val))
        
        remaining = num_samples
        while remaining > 0:
            count = min(remaining, chunk_size)
            wav.writeframes(tone_block[: count * 2])
            remaining -= count


@pytest.mark.asyncio
async def test_full_pipeline_long_audio():
    storage = get_storage_service()
    
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name

    try:
        # Generate 65-second audio
        generate_long_wav(wav_path, duration_sec=65.0)
        file_size = os.path.getsize(wav_path)

        note_id = "test-e2e-pipeline-note-01"
        storage_key = f"audio/{note_id}/long_recording.wav"

        with open(wav_path, "rb") as f:
            storage.upload_file(f, storage_key, "audio/wav")

        # Create note record in DB
        async with AsyncSessionLocal() as session:
            note = AudioNote(
                id=note_id,
                title="Executive Briefing Long Audio",
                original_filename="long_recording.wav",
                file_size_bytes=file_size,
                mime_type="audio/wav",
                storage_backend="local",
                storage_path=storage_key,
                audio_url=f"/api/v1/notes/{note_id}/audio",
                status=ProcessingStatus.UPLOADED,
                progress_percentage=0,
                current_step="File uploaded",
                language_code="en-IN",
            )
            session.add(note)
            await session.commit()

        # Run background job runner
        await process_audio_note_job(note_id)

        # Verify final record in DB
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(AudioNote).where(AudioNote.id == note_id))
            processed_note = res.scalar_one()

            assert processed_note.status == ProcessingStatus.COMPLETED
            assert processed_note.progress_percentage == 100
            assert processed_note.duration_seconds >= 64.0
            assert processed_note.raw_transcript is not None
            assert len(processed_note.raw_transcript) > 0
            assert processed_note.summary_tldr is not None
            assert len(processed_note.summary_key_points) > 0
            assert len(processed_note.transcript_segments) >= 2  # Proves chunking occurred!
            assert processed_note.asr_engine_used == "gnani-chunked-rest"

    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
