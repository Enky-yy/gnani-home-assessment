import os
import json
import logging
import subprocess
from dataclasses import dataclass
from typing import List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class AudioMetadata:
    duration_seconds: float
    format_name: str
    sample_rate: int
    channels: int
    bit_rate: Optional[int] = None
    codec_name: Optional[str] = None


@dataclass
class AudioChunk:
    chunk_index: int
    file_path: str
    start_time: float
    end_time: float
    duration: float


class AudioProcessingError(Exception):
    """Custom exception raised when audio validation or processing fails."""
    pass


class AudioService:
    """Service for validating, probing, downsampling, and chunking audio files."""

    @staticmethod
    def inspect_audio(file_path: str) -> AudioMetadata:
        """Run ffprobe to extract audio stream metadata and validate readability."""
        if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
            raise AudioProcessingError("Audio file is empty or missing on disk.")

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path,
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            probe_data = json.loads(result.stdout)
        except subprocess.CalledProcessError as e:
            logger.error(f"ffprobe failed on {file_path}: {e.stderr}")
            raise AudioProcessingError(f"Corrupted or invalid audio file format: {e.stderr.strip() or 'Cannot decode'}")
        except Exception as e:
            logger.error(f"Unexpected error inspecting audio {file_path}: {e}")
            raise AudioProcessingError(f"Failed to inspect audio metadata: {str(e)}")

        streams = probe_data.get("streams", [])
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        format_info = probe_data.get("format", {})
        duration_str = format_info.get("duration")

        if not duration_str and audio_stream:
            duration_str = audio_stream.get("duration")

        if not duration_str:
            raise AudioProcessingError("Unable to determine audio duration. File may be corrupted or headers missing.")

        try:
            duration = float(duration_str)
        except ValueError:
            raise AudioProcessingError(f"Invalid duration value returned: {duration_str}")

        if duration <= 0:
            raise AudioProcessingError("Audio file duration is zero seconds.")

        sample_rate = int(audio_stream.get("sample_rate", 16000)) if audio_stream else 16000
        channels = int(audio_stream.get("channels", 1)) if audio_stream else 1
        codec = audio_stream.get("codec_name") if audio_stream else "unknown"
        bit_rate = int(format_info.get("bit_rate")) if format_info.get("bit_rate") else None

        return AudioMetadata(
            duration_seconds=duration,
            format_name=format_info.get("format_name", "unknown"),
            sample_rate=sample_rate,
            channels=channels,
            bit_rate=bit_rate,
            codec_name=codec,
        )

    @staticmethod
    def chunk_audio(
        input_path: str,
        output_dir: str,
        chunk_duration_sec: float = 24.0,
        overlap_sec: float = 1.0,
    ) -> List[AudioChunk]:
        """
        Split a long audio file into overlapping chunks for chunked REST ASR.
        Chunk duration is capped at 24s to guarantee compliance with Gnani's 30s ceiling.
        """
        meta = AudioService.inspect_audio(input_path)
        total_duration = meta.duration_seconds
        os.makedirs(output_dir, exist_ok=True)

        chunks: List[AudioChunk] = []
        current_start = 0.0
        chunk_idx = 0

        # Step size is chunk_duration - overlap
        step = max(chunk_duration_sec - overlap_sec, 5.0)

        while current_start < total_duration:
            chunk_len = min(chunk_duration_sec, total_duration - current_start)
            current_end = current_start + chunk_len
            chunk_file = os.path.join(output_dir, f"chunk_{chunk_idx:04d}.wav")

            # Extract chunk using ffmpeg with -ss and -t for precise duration capping
            cmd = [
                "ffmpeg",
                "-y",
                "-ss", str(current_start),
                "-i", input_path,
                "-t", str(chunk_len),
                "-ar", "16000",
                "-ac", "1",
                "-c:a", "pcm_s16le",
                chunk_file,
            ]

            try:
                subprocess.run(cmd, capture_output=True, check=True)
            except subprocess.CalledProcessError as e:
                logger.error(f"FFmpeg chunking error at index {chunk_idx}: {e.stderr}")
                raise AudioProcessingError(f"Failed to slice audio chunk {chunk_idx}: {e.stderr}")

            chunks.append(
                AudioChunk(
                    chunk_index=chunk_idx,
                    file_path=chunk_file,
                    start_time=current_start,
                    end_time=current_end,
                    duration=chunk_len,
                )
            )

            if current_end >= total_duration:
                break

            current_start += step
            chunk_idx += 1

        logger.info(f"Split {input_path} ({total_duration:.1f}s) into {len(chunks)} chunks of <={chunk_duration_sec}s.")
        return chunks

    @staticmethod
    def normalize_to_wav(input_path: str, output_path: str, loudness: bool = True) -> str:
        """Transcode any audio file to clean 16kHz mono 16-bit PCM WAV.

        Applies a speech-band filter chain (80Hz highpass to cut rumble/wind,
        7.5kHz lowpass to cut hiss) plus EBU R128 loudness normalization so
        quiet phone recordings and loud compressed clips (e.g. YouTube rips)
        hit the ASR engine at a consistent level.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        audio_filter = "highpass=f=80,lowpass=f=7500"
        if loudness:
            audio_filter += ",loudnorm=I=-16:TP=-1.5:LRA=11"
        cmd = [
            "ffmpeg",
            "-y",
            "-i", input_path,
            "-ar", "16000",
            "-ac", "1",
            "-af", audio_filter,
            "-c:a", "pcm_s16le",
            output_path,
        ]
        try:
            subprocess.run(cmd, capture_output=True, check=True)
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg normalization failed: {e.stderr}")
            raise AudioProcessingError(f"Failed to transcode audio: {e.stderr}")
