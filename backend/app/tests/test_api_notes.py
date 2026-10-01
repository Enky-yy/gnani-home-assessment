import io
import math
import struct
import wave
import pytest
from httpx import AsyncClient


def create_in_memory_wav(duration_sec: float = 2.0, sample_rate: int = 16000) -> io.BytesIO:
    """Generate in-memory WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(sample_rate)
        num_samples = int(duration_sec * sample_rate)
        raw_data = bytearray()
        for i in range(num_samples):
            value = int(32767.0 * 0.3 * math.sin(2.0 * math.pi * 440.0 * i / sample_rate))
            raw_data.extend(struct.pack("<h", value))
        wav.writeframes(raw_data)
    buf.seek(0)
    return buf


@pytest.mark.asyncio
async def test_health_check(async_client: AsyncClient):
    resp = await async_client.get("/api/v1/health")
    assert resp.status_code == 200
    data = resp.json()
    assert "status" in data
    assert "database" in data
    assert "storage" in data


@pytest.mark.asyncio
async def test_list_models(async_client: AsyncClient):
    resp = await async_client.get("/v1/models")
    assert resp.status_code == 200
    data = resp.json()
    assert data["object"] == "list"
    assert len(data["data"]) >= 3
    assert any(m["id"] == "gnani-prisma-v2.5" for m in data["data"])


@pytest.mark.asyncio
async def test_upload_invalid_extension(async_client: AsyncClient):
    fake_file = io.BytesIO(b"Hello world text file")
    resp = await async_client.post(
        "/api/v1/notes",
        files={"file": ("document.txt", fake_file, "text/plain")},
        data={"title": "Invalid Note"},
    )
    assert resp.status_code == 400
    assert "Unsupported audio format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_and_retrieve_note(async_client: AsyncClient):
    wav_buf = create_in_memory_wav(duration_sec=2.0)
    
    # 1. Upload
    upload_resp = await async_client.post(
        "/api/v1/notes",
        files={"file": ("test_voice_note.wav", wav_buf, "audio/wav")},
        data={"title": "Test Voice Recording", "language_code": "en-IN"},
    )
    assert upload_resp.status_code == 202
    note_data = upload_resp.json()
    note_id = note_data["id"]
    assert note_data["title"] == "Test Voice Recording"
    assert note_data["status"] == "UPLOADED"

    # 2. Check status polling endpoint
    status_resp = await async_client.get(f"/api/v1/notes/{note_id}/status")
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == note_id
    assert "progress_percentage" in status_data
    assert "current_step" in status_data

    # 3. Retrieve in list
    list_resp = await async_client.get("/api/v1/notes")
    assert list_resp.status_code == 200
    notes_list = list_resp.json()
    assert any(n["id"] == note_id for n in notes_list)

    # 4. Update title
    patch_resp = await async_client.patch(
        f"/api/v1/notes/{note_id}/title",
        json={"title": "Renamed Voice Recording"},
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Renamed Voice Recording"

    # 5. Delete note
    del_resp = await async_client.delete(f"/api/v1/notes/{note_id}")
    assert del_resp.status_code == 204

    # 6. Verify 404 after deletion
    get_after_del = await async_client.get(f"/api/v1/notes/{note_id}")
    assert get_after_del.status_code == 404
