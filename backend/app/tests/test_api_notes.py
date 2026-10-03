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
async def test_upload_invalid_extension(async_client: AsyncClient, auth_headers: dict):
    fake_file = io.BytesIO(b"Hello world text file")
    resp = await async_client.post(
        "/api/v1/notes",
        files={"file": ("document.txt", fake_file, "text/plain")},
        data={"title": "Invalid Note"},
        headers=auth_headers,
    )
    assert resp.status_code == 400
    assert "Unsupported audio format" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_upload_and_retrieve_note(async_client: AsyncClient, auth_headers: dict):
    wav_buf = create_in_memory_wav(duration_sec=2.0)
    
    # 1. Upload
    upload_resp = await async_client.post(
        "/api/v1/notes",
        files={"file": ("test_voice_note.wav", wav_buf, "audio/wav")},
        data={"title": "Test Voice Recording", "language_code": "en-IN"},
        headers=auth_headers,
    )
    assert upload_resp.status_code == 202
    note_data = upload_resp.json()
    note_id = note_data["id"]
    assert note_data["title"] == "Test Voice Recording"
    assert note_data["status"] == "UPLOADED"

    # 2. Check status polling endpoint
    status_resp = await async_client.get(f"/api/v1/notes/{note_id}/status", headers=auth_headers)
    assert status_resp.status_code == 200
    status_data = status_resp.json()
    assert status_data["id"] == note_id
    assert "progress_percentage" in status_data
    assert "current_step" in status_data

    # 3. Retrieve in list
    list_resp = await async_client.get("/api/v1/notes", headers=auth_headers)
    assert list_resp.status_code == 200
    notes_list = list_resp.json()
    assert any(n["id"] == note_id for n in notes_list)

    # 4. Update title
    patch_resp = await async_client.patch(
        f"/api/v1/notes/{note_id}/title",
        json={"title": "Renamed Voice Recording"},
        headers=auth_headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Renamed Voice Recording"

    # 5. Delete note
    del_resp = await async_client.delete(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert del_resp.status_code == 204

    # 6. Verify 404 after deletion
    get_after_del = await async_client.get(f"/api/v1/notes/{note_id}", headers=auth_headers)
    assert get_after_del.status_code == 404


@pytest.mark.asyncio
async def test_resummarize_existing_transcript(async_client: AsyncClient, db_session, auth_headers: dict):
    from app.models.audio_note import AudioNote, ProcessingStatus

    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = me.json()["id"]
    note = AudioNote(
        id="test-resum-01",
        owner_id=owner_id,
        title="Resum Test",
        original_filename="r.wav",
        file_size_bytes=10,
        mime_type="audio/wav",
        storage_backend="local",
        storage_path="audio/test-resum-01/r.wav",
        status=ProcessingStatus.COMPLETED,
        progress_percentage=100,
        current_step="done",
        language_code="en-IN",
        raw_transcript="The team agreed to launch on Friday. Rahul will prepare the release notes. The budget was approved unanimously.",
    )
    db_session.add(note)
    await db_session.commit()

    resp = await async_client.post("/api/v1/notes/test-resum-01/summarize", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["summary_tldr"]
    # Test env has no LLM keys -> extractive fallback, still labeled
    assert data["llm_model_used"] == "langchain-extractive-fallback"


@pytest.mark.asyncio
async def test_resummarize_without_transcript_rejected(async_client: AsyncClient, db_session, auth_headers: dict):
    from app.models.audio_note import AudioNote, ProcessingStatus

    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = me.json()["id"]
    note = AudioNote(
        id="test-resum-02",
        owner_id=owner_id,
        title="Empty Note",
        original_filename="e.wav",
        file_size_bytes=10,
        mime_type="audio/wav",
        storage_backend="local",
        storage_path="audio/test-resum-02/e.wav",
        status=ProcessingStatus.FAILED,
        progress_percentage=100,
        current_step="failed",
        language_code="en-IN",
    )
    db_session.add(note)
    await db_session.commit()

    resp = await async_client.post("/api/v1/notes/test-resum-02/summarize", headers=auth_headers)
    assert resp.status_code == 400

    resp404 = await async_client.post("/api/v1/notes/does-not-exist/summarize", headers=auth_headers)
    assert resp404.status_code == 404


@pytest.mark.asyncio
async def test_audio_url_handoff(async_client: AsyncClient, db_session, auth_headers: dict):
    from app.models.audio_note import AudioNote, ProcessingStatus

    me = await async_client.get("/api/v1/auth/me", headers=auth_headers)
    owner_id = me.json()["id"]
    db_session.add(
        AudioNote(
            id="test-aurl-01",
            owner_id=owner_id,
            title="URL Test",
            original_filename="u.wav",
            file_size_bytes=10,
            mime_type="audio/wav",
            storage_backend="local",
            storage_path="audio/test-aurl-01/u.wav",
            status=ProcessingStatus.COMPLETED,
            progress_percentage=100,
            current_step="done",
            language_code="en-IN",
        )
    )
    await db_session.commit()

    # no token -> 401 (player must authenticate)
    assert (await async_client.get("/api/v1/notes/test-aurl-01/audio-url")).status_code == 401
    # owner -> local stream path handoff
    ok = await async_client.get("/api/v1/notes/test-aurl-01/audio-url", headers=auth_headers)
    assert ok.status_code == 200
    assert ok.json()["url"].endswith("/api/v1/notes/test-aurl-01/audio")
