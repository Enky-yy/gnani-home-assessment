import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database import AsyncSessionLocal, init_db
from app.models.audio_note import AudioNote, ProcessingStatus


DEMO_NOTES = [
    {
        "title": "Quarterly Product Strategy & Voice AI Roadmap",
        "original_filename": "q3_product_strategy_sync.mp3",
        "file_size_bytes": 4829120,
        "mime_type": "audio/mpeg",
        "duration_seconds": 154.5,
        "storage_backend": "s3",
        "storage_path": "audio/demo/q3_product_strategy_sync.mp3",
        "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-1.mp3",
        "status": ProcessingStatus.COMPLETED,
        "progress_percentage": 100,
        "current_step": "Processing completed successfully",
        "language_code": "en-IN",
        "asr_engine_used": "gnani-chunked-rest",
        "raw_transcript": (
            "Welcome everyone to our Q3 Voice AI roadmap meeting. Today we are reviewing the rollout "
            "of our automated audio notes pipeline. First, we have successfully integrated Gnani's "
            "speech recognition API with AWS S3 storage. Our latency benchmarks show sub-minute transcription "
            "even for long audio recordings over two minutes. Second, we decided to use Gemini 2.5 Flash for "
            "instant summarization, structured action items, and topic extraction. Finally, we need to ensure "
            "that the Docker Compose deployment on AWS EC2 is finalized before the weekend cutoff. "
            "Rahul will take ownership of the Nginx reverse proxy configuration and SSL certificate provisioning."
        ),
        "transcript_segments": [
            {
                "start": 0.0,
                "end": 28.5,
                "text": "Welcome everyone to our Q3 Voice AI roadmap meeting. Today we are reviewing the rollout of our automated audio notes pipeline.",
            },
            {
                "start": 29.0,
                "end": 68.0,
                "text": "First, we have successfully integrated Gnani's speech recognition API with AWS S3 storage. Our latency benchmarks show sub-minute transcription even for long audio recordings over two minutes.",
            },
            {
                "start": 68.5,
                "end": 112.0,
                "text": "Second, we decided to use Gemini 2.5 Flash for instant summarization, structured action items, and topic extraction.",
            },
            {
                "start": 112.5,
                "end": 154.5,
                "text": "Finally, we need to ensure that the Docker Compose deployment on AWS EC2 is finalized before the weekend cutoff. Rahul will take ownership of Nginx reverse proxy configuration.",
            },
        ],
        "summary_tldr": (
            "The engineering team reviewed the Voice AI audio notes pipeline integration between Gnani STT and AWS S3. "
            "Benchmarking confirmed sub-minute latency for audio over two minutes, and action items were assigned for AWS EC2 deployment."
        ),
        "summary_key_points": [
            "Gnani Voice AI ASR successfully integrated with AWS S3 object storage.",
            "Sub-minute transcription latency achieved on multi-minute audio recordings.",
            "Gemini Flash selected for real-time structured summarization and action items.",
            "AWS EC2 production deployment prioritized for weekend deadline.",
        ],
        "summary_action_items": [
            "Rahul to finalize Docker Compose setup and Nginx reverse proxy with SSL.",
            "Conduct end-to-end smoke testing on live EC2 public endpoint.",
            "Document long-audio chunking architecture in the /architecture page.",
        ],
        "summary_sentiment": "Collaborative",
        "llm_model_used": "gemini-2.5-flash",
    },
    {
        "title": "Customer Feedback & STT Latency Analysis",
        "original_filename": "customer_interview_bangalore.wav",
        "file_size_bytes": 8345100,
        "mime_type": "audio/wav",
        "duration_seconds": 128.2,
        "storage_backend": "s3",
        "storage_path": "audio/demo/customer_interview_bangalore.wav",
        "audio_url": "https://www.soundhelix.com/examples/mp3/SoundHelix-Song-2.mp3",
        "status": ProcessingStatus.COMPLETED,
        "progress_percentage": 100,
        "current_step": "Processing completed successfully",
        "language_code": "en-IN",
        "asr_engine_used": "gnani-chunked-rest",
        "raw_transcript": (
            "We conducted user interviews regarding audio note taking in field operations. "
            "Users highlighted that when files exceed 60 seconds, other platforms freeze or drop connections. "
            "Having visible step-by-step progress tracking and instant playback creates immediate trust. "
            "They also requested automatic bullet points and action item detection for meeting minutes."
        ),
        "transcript_segments": [
            {
                "start": 0.0,
                "end": 42.0,
                "text": "We conducted user interviews regarding audio note taking in field operations.",
            },
            {
                "start": 42.5,
                "end": 85.0,
                "text": "Users highlighted that when files exceed 60 seconds, other platforms freeze or drop connections.",
            },
            {
                "start": 85.5,
                "end": 128.2,
                "text": "Having visible step-by-step progress tracking and instant playback creates immediate trust. They also requested automatic bullet points and action item detection.",
            },
        ],
        "summary_tldr": (
            "Field user interviews emphasized the critical importance of visible progress indicators for long recordings "
            "and praised automated action item extraction."
        ),
        "summary_key_points": [
            "Users experience connection drops on competitor platforms during long uploads.",
            "Step-by-step progress tickers build high user trust.",
            "High demand for automated action item checklist extraction.",
        ],
        "summary_action_items": [
            "Ensure failure states and retry buttons are prominently highlighted in the UI.",
            "Add one-click markdown copy for extracted action items.",
        ],
        "summary_sentiment": "Constructive",
        "llm_model_used": "gemini-2.5-flash",
    },
]


async def seed_data():
    print("Initializing database tables...")
    await init_db()

    async with AsyncSessionLocal() as session:
        for idx, item in enumerate(DEMO_NOTES):
            note = AudioNote(
                id=str(uuid.uuid4()),
                title=item["title"],
                original_filename=item["original_filename"],
                file_size_bytes=item["file_size_bytes"],
                mime_type=item["mime_type"],
                duration_seconds=item["duration_seconds"],
                storage_backend=item["storage_backend"],
                storage_path=item["storage_path"],
                audio_url=item["audio_url"],
                status=item["status"],
                progress_percentage=item["progress_percentage"],
                current_step=item["current_step"],
                language_code=item["language_code"],
                asr_engine_used=item["asr_engine_used"],
                raw_transcript=item["raw_transcript"],
                transcript_segments=item["transcript_segments"],
                summary_tldr=item["summary_tldr"],
                summary_key_points=item["summary_key_points"],
                summary_action_items=item["summary_action_items"],
                summary_sentiment=item["summary_sentiment"],
                llm_model_used=item["llm_model_used"],
                created_at=datetime.now(timezone.utc) - timedelta(hours=(idx + 1) * 3),
                updated_at=datetime.now(timezone.utc) - timedelta(hours=(idx + 1) * 3),
            )
            session.add(note)

        await session.commit()
        print(f"Successfully seeded {len(DEMO_NOTES)} production demo audio notes!")


if __name__ == "__main__":
    asyncio.run(seed_data())
