import os
import math
import struct
import wave
import tempfile
import pytest
from app.services.audio import AudioService, AudioProcessingError


def create_dummy_wav(file_path: str, duration_sec: float = 3.0, sample_rate: int = 16000):
    """Generate a clean synthetic WAV file for testing without external tools."""
    num_samples = int(duration_sec * sample_rate)
    with wave.open(file_path, "wb") as wav:
        wav.setnchannels(1)  # Mono
        wav.setsampwidth(2)  # 16-bit
        wav.setframerate(sample_rate)
        
        # 440 Hz concert pitch tone
        raw_data = bytearray()
        for i in range(num_samples):
            value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            raw_data.extend(struct.pack("<h", value))
        wav.writeframes(raw_data)


def test_inspect_valid_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name

    try:
        create_dummy_wav(wav_path, duration_sec=2.5, sample_rate=16000)
        meta = AudioService.inspect_audio(wav_path)
        assert meta.duration_seconds >= 2.4
        assert meta.duration_seconds <= 2.6
        assert meta.sample_rate == 16000
        assert meta.channels == 1
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)


def test_inspect_corrupted_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        corrupted_path = tf.name
        tf.write(b"NOT_A_VALID_AUDIO_HEADER_CORRUPTED_FILE_DATA")

    try:
        with pytest.raises(AudioProcessingError) as exc_info:
            AudioService.inspect_audio(corrupted_path)
        assert "Corrupted or invalid" in str(exc_info.value)
    finally:
        if os.path.exists(corrupted_path):
            os.remove(corrupted_path)


def test_inspect_empty_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        empty_path = tf.name

    try:
        with pytest.raises(AudioProcessingError) as exc_info:
            AudioService.inspect_audio(empty_path)
        assert "empty or missing" in str(exc_info.value)
    finally:
        if os.path.exists(empty_path):
            os.remove(empty_path)


def test_chunking_audio():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name

    output_dir = tempfile.mkdtemp()
    try:
        # Create a 6-second audio and split into 3-second chunks with 0.5s overlap
        create_dummy_wav(wav_path, duration_sec=6.0, sample_rate=16000)
        chunks = AudioService.chunk_audio(
            input_path=wav_path,
            output_dir=output_dir,
            chunk_duration_sec=3.0,
            overlap_sec=0.5,
        )
        assert len(chunks) >= 2
        for c in chunks:
            assert os.path.exists(c.file_path)
            assert c.duration > 0
    finally:
        if os.path.exists(wav_path):
            os.remove(wav_path)
        import shutil
        shutil.rmtree(output_dir, ignore_errors=True)
