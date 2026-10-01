import os
import asyncio
import logging
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
import httpx
from app.config import settings
from app.services.audio import AudioService, AudioChunk

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionResult:
    raw_transcript: str
    segments: List[Dict[str, Any]]
    engine_used: str
    job_id: Optional[str] = None
    language_code: str = "en-IN"


class GnaniSTTError(Exception):
    """Exception raised when Gnani ASR returns an error or times out."""
    def __init__(self, message: str, status_code: Optional[int] = None, retryable: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.retryable = retryable


class GnaniSTTClient:
    """Production client for Gnani Voice AI STT APIs with REST, Chunked, and Batch fallback."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GNANI_API_KEY
        self.rest_endpoint = settings.GNANI_REST_ENDPOINT
        self.batch_endpoint = settings.GNANI_BATCH_JOBS_ENDPOINT
        self.base_url = settings.GNANI_BASE_URL
        self.is_demo_mode = not bool(self.api_key and self.api_key.strip())

        if self.is_demo_mode:
            logger.warning(
                "GNANI_API_KEY not configured. Running in Demo Simulation Mode. "
                "Provide a valid Gnani API key in .env or dashboard to use live Gnani Prisma ASR."
            )
        else:
            logger.info("Initialized Gnani STT Client with active API key.")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "X-API-Key-ID": self.api_key or "",
            "Accept": "application/json",
        }

    async def transcribe_short_audio(
        self,
        file_path: str,
        language_code: str = "en-IN",
        max_retries: int = 3,
    ) -> str:
        """
        Transcribe an audio clip (<= GNANI_MAX_REST_AUDIO_SECONDS, 25s by default)
        using Gnani's synchronous REST STT endpoint.
        Includes exponential backoff retry for transient network and 429/5xx errors.
        """
        if self.is_demo_mode:
            await asyncio.sleep(1.5)  # Simulate network latency
            return self._generate_simulated_text(file_path, language_code)

        if not os.path.exists(file_path):
            raise GnaniSTTError(f"Audio file not found: {file_path}")

        # Pre-flight duration guard: Gnani REST API strictly rejects files > 30 seconds
        try:
            meta = AudioService.inspect_audio(file_path)
            if meta.duration_seconds > 28.0:
                logger.warning(
                    f"Audio {file_path} duration ({meta.duration_seconds:.1f}s) exceeds Gnani's 30s REST limit. Auto-delegating to chunked transcriber."
                )
                chunk_res = await self.transcribe_long_audio_chunked(file_path, language_code)
                return chunk_res.raw_transcript
        except GnaniSTTError:
            raise
        except Exception as e:
            logger.debug(f"Audio pre-inspection check bypassed: {e}")

        file_name = os.path.basename(file_path)
        mime_type = "audio/wav" if file_path.endswith(".wav") else "audio/mpeg"

        for attempt in range(1, max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=45.0) as client:
                    with open(file_path, "rb") as f:
                        files = {"audio_file": (file_name, f, mime_type)}
                        data = {
                            "language_code": language_code,
                            "format": "transcribe",
                            "itn_native_numerals": "false",
                        }

                        logger.info(f"Dispatching to Gnani REST STT (Attempt {attempt}/{max_retries}): {self.rest_endpoint}")
                        response = await client.post(
                            self.rest_endpoint,
                            headers=self._get_headers(),
                            files=files,
                            data=data,
                        )

                    if response.status_code == 200:
                        res_json = response.json()
                        transcript = res_json.get("transcript", "").strip()
                        logger.info(f"Gnani REST STT success: received {len(transcript)} chars.")
                        return transcript
                    
                    elif response.status_code == 429:
                        wait_sec = attempt * 2.0
                        logger.warning(f"Gnani rate limit (429) hit. Backing off for {wait_sec}s...")
                        if attempt == max_retries:
                            raise GnaniSTTError("Gnani STT rate limit exceeded after multiple retries.", status_code=429)
                        await asyncio.sleep(wait_sec)

                    elif response.status_code in (500, 502, 503, 504):
                        wait_sec = attempt * 2.0
                        logger.warning(f"Gnani server error ({response.status_code}). Backing off for {wait_sec}s...")
                        if attempt == max_retries:
                            raise GnaniSTTError(f"Gnani STT server error: {response.text}", status_code=response.status_code, retryable=True)
                        await asyncio.sleep(wait_sec)

                    else:
                        error_body = response.text
                        logger.error(f"Gnani REST STT error {response.status_code}: {error_body}")
                        raise GnaniSTTError(f"Gnani STT rejected request ({response.status_code}): {error_body}", status_code=response.status_code)

            except (httpx.TimeoutException, httpx.NetworkError) as e:
                logger.warning(f"Network error communicating with Gnani STT (Attempt {attempt}): {e}")
                if attempt == max_retries:
                    raise GnaniSTTError(f"Gnani STT network connection timed out: {e}", retryable=True)
                await asyncio.sleep(attempt * 2.0)

        raise GnaniSTTError("Failed to obtain transcript from Gnani REST STT.")

    async def transcribe_long_audio_chunked(
        self,
        file_path: str,
        language_code: str = "en-IN",
        scratch_dir: str = "/tmp/audio_chunks",
        progress_callback=None,
    ) -> TranscriptionResult:
        """
        Transcribe audio of arbitrary duration by slicing into ~24s chunks with overlap,
        transcribing chunks concurrently with bounded concurrency, and stitching segments.
        Guarantees that each chunk is strictly under Gnani's 30s maximum limit.
        """
        os.makedirs(scratch_dir, exist_ok=True)
        meta = AudioService.inspect_audio(file_path)
        logger.info(f"Beginning chunked transcription for audio duration: {meta.duration_seconds:.2f}s")

        chunks = AudioService.chunk_audio(
            input_path=file_path,
            output_dir=scratch_dir,
            chunk_duration_sec=24.0,
            overlap_sec=1.0,
        )

        total_chunks = len(chunks)
        semaphore = asyncio.Semaphore(1)  # Serialized execution to prevent Gnani 429 rate limits
        completed_count = 0
        segments: List[Dict[str, Any]] = []

        async def process_chunk(chunk: AudioChunk) -> Dict[str, Any]:
            nonlocal completed_count
            async with semaphore:
                try:
                    text = await self.transcribe_short_audio(chunk.file_path, language_code=language_code)
                except GnaniSTTError as ge:
                    logger.warning(
                        f"Gnani chunk {chunk.chunk_index} ({chunk.start_time:.1f}-{chunk.end_time:.1f}s) notice: {ge}. Continuing..."
                    )
                    text = ""
                except Exception as e:
                    logger.warning(
                        f"Unexpected error on chunk {chunk.chunk_index}: {e}. Continuing..."
                    )
                    text = ""

                completed_count += 1
                if progress_callback:
                    # Progress spans from 25% to 70%
                    pct = int(25 + (completed_count / total_chunks) * 45)
                    await progress_callback(pct, f"Transcribed chunk {completed_count}/{total_chunks}")
                
                # Small pacing sleep to respect Gnani API limits
                await asyncio.sleep(0.5)
                return {
                    "start": round(chunk.start_time, 2),
                    "end": round(chunk.end_time, 2),
                    "text": text,
                }

        # Process chunks concurrently
        chunk_tasks = [process_chunk(c) for c in chunks]
        results = await asyncio.gather(*chunk_tasks)

        # Sort results strictly by start time
        results.sort(key=lambda x: x["start"])

        # Stitch full transcript text
        full_text_parts = [r["text"] for r in results if r["text"].strip()]
        full_transcript = " ".join(full_text_parts) if full_text_parts else "[No speech detected in recording]"

        # Cleanup chunk files
        for c in chunks:
            try:
                if os.path.exists(c.file_path):
                    os.remove(c.file_path)
            except Exception:
                pass

        return TranscriptionResult(
            raw_transcript=full_transcript,
            segments=results,
            engine_used="gnani-chunked-rest",
            language_code=language_code,
        )

    async def transcribe(
        self,
        file_path: str,
        duration_seconds: float,
        language_code: str = "en-IN",
        scratch_dir: str = "/tmp/audio_chunks",
        progress_callback=None,
    ) -> TranscriptionResult:
        """
        Unified dispatch:
        If duration <= GNANI_MAX_REST_AUDIO_SECONDS (25s default): Single-shot Gnani REST STT.
        If duration > threshold: Resilient Chunked & Stitched Gnani STT.
        """
        if duration_seconds <= settings.GNANI_MAX_REST_AUDIO_SECONDS:
            if progress_callback:
                await progress_callback(40, "Transcribing with Gnani REST ASR...")
            text = await self.transcribe_short_audio(file_path, language_code)
            if progress_callback:
                await progress_callback(68, "ASR transcription finalized")
            return TranscriptionResult(
                raw_transcript=text,
                segments=[{"start": 0.0, "end": round(duration_seconds, 2), "text": text}],
                engine_used="gnani-rest-single",
                language_code=language_code,
            )
        else:
            return await self.transcribe_long_audio_chunked(
                file_path=file_path,
                language_code=language_code,
                scratch_dir=scratch_dir,
                progress_callback=progress_callback,
            )

    def _generate_simulated_text(self, file_path: str, language_code: str) -> str:
        """Realistic simulated transcription fallback when GNANI_API_KEY is not configured."""
        base_name = os.path.basename(file_path).lower()
        if "meeting" in base_name or "discussion" in base_name:
            return (
                "Good morning everyone. Thank you for joining today's voice engineering sync. "
                "We discussed integrating Gnani's speech-to-text platform with our AWS S3 storage pipeline. "
                "Key takeaways: we must ensure that long audio files over two minutes are properly sliced "
                "and processed asynchronously to prevent connection timeouts. Next steps: finalize the "
                "FastAPI database models, deploy to AWS EC2, and prepare the architecture documentation."
            )
        return (
            "Welcome to the audio notes platform. This is a demonstration recording showcasing "
            "seamless voice-to-text processing powered by Gnani AI. Audio files are validated, "
            "streamed to secure AWS S3 buckets, and transcribed into high-fidelity text. "
            "The background worker orchestrates asynchronous recognition and synthesizes a structured summary."
        )
