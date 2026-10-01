import os
import math
import struct
import wave
import tempfile
import pytest
from app.services.audio import AudioService, AudioProcessingError
from app.services.gnani_stt import GnaniSTTClient, GnaniSTTError, merge_overlap_texts


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


def test_normalize_to_wav_produces_16k_mono():
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        src_path = tf.name
    out_path = src_path + ".norm16k.wav"
    try:
        # 44.1kHz stereo source
        num_samples = 44100
        with wave.open(src_path, "wb") as wav:
            wav.setnchannels(2)
            wav.setsampwidth(2)
            wav.setframerate(44100)
            raw = bytearray()
            for i in range(num_samples):
                v = int(10000.0 * math.sin(2.0 * math.pi * 440.0 * i / 44100))
                raw.extend(struct.pack("<hh", v, v))
            wav.writeframes(raw)
        AudioService.normalize_to_wav(src_path, out_path)
        meta = AudioService.inspect_audio(out_path)
        assert meta.sample_rate == 16000
        assert meta.channels == 1
        assert abs(meta.duration_seconds - 1.0) < 0.15
    finally:
        for p in (src_path, out_path):
            if os.path.exists(p):
                os.remove(p)


def test_merge_overlap_texts_collapses_seams():
    a = "welcome to the audio notes platform demo today"
    b = "notes platform demo today showcasing voice to text"
    assert merge_overlap_texts([a, b]) == "welcome to the audio notes platform demo today showcasing voice to text"


def test_merge_overlap_texts_ignores_short_bigrams():
    # 2-word overlaps (e.g. "of the") are too common to trust — left duplicated
    # rather than risk dropping real words on a false match.
    a = "welcome to the audio notes platform demo"
    b = "platform demo showcasing voice to text"
    assert merge_overlap_texts([a, b]) == a + " " + b


def test_merge_overlap_texts_case_and_punctuation_insensitive():
    a = "Hello, WORLD. How are you"
    b = "how are YOU today my friend"
    assert merge_overlap_texts([a, b]) == "Hello, WORLD. How are you today my friend"


def test_merge_overlap_texts_no_overlap_joins():
    assert merge_overlap_texts(["alpha beta", "gamma delta"]) == "alpha beta gamma delta"
    assert merge_overlap_texts([]) == ""
    assert merge_overlap_texts(["  ", "only"]) == "only"


def _make_wav(path: str, duration_sec: float = 6.0):
    create_dummy_wav(path, duration_sec=duration_sec)


@pytest.mark.asyncio
async def test_chunked_all_fail_raises_instead_of_fake_completed(tmp_path):
    """Expired key (401 on every chunk) must raise -> job_runner marks FAILED."""
    wav_path = str(tmp_path / "src.wav")
    _make_wav(wav_path)
    client = GnaniSTTClient(api_key="expired-key")

    async def boom(*args, **kwargs):
        raise GnaniSTTError("Gnani STT rejected request (401): Unauthorized", status_code=401)

    import unittest.mock as mock
    with mock.patch.object(client, "transcribe_short_audio", side_effect=boom):
        with pytest.raises(GnaniSTTError, match="All .* chunks failed"):
            await client.transcribe_long_audio_chunked(wav_path, scratch_dir=str(tmp_path / "chunks"))


@pytest.mark.asyncio
async def test_chunked_partial_failure_still_returns(tmp_path):
    """One bad chunk must not kill the note — surviving text is returned."""
    wav_path = str(tmp_path / "src.wav")
    _make_wav(wav_path, duration_sec=30.0)  # forces >= 2 chunks
    client = GnaniSTTClient(api_key="expired-key")
    calls = {"n": 0}

    async def flaky(file_path, language_code="en-IN", **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise GnaniSTTError("boom", status_code=500, retryable=True)
        return "hello world from chunk"

    import unittest.mock as mock
    with mock.patch.object(client, "transcribe_short_audio", side_effect=flaky):
        res = await client.transcribe_long_audio_chunked(wav_path, scratch_dir=str(tmp_path / "chunks"))
    assert "hello world from chunk" in res.raw_transcript
    assert res.engine_used == "gnani-chunked-rest"
