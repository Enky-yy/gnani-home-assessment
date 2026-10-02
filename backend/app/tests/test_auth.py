import io
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


async def _register(async_client: AsyncClient, email: str, password: str = "password123"):
    resp = await async_client.post("/api/v1/auth/register", json={"email": email, "password": password})
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _login_headers(async_client: AsyncClient, email: str, password: str = "password123"):
    resp = await async_client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


@pytest.mark.asyncio
async def test_register_login_me(async_client: AsyncClient):
    user = await _register(async_client, "alice@example.com")
    assert user["email"] == "alice@example.com"
    assert "id" in user

    headers = await _login_headers(async_client, "alice@example.com")
    me = await async_client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_register_duplicate_rejected(async_client: AsyncClient):
    await _register(async_client, "bob@example.com")
    dup = await async_client.post(
        "/api/v1/auth/register", json={"email": "bob@example.com", "password": "password123"}
    )
    assert dup.status_code == 400


@pytest.mark.asyncio
async def test_register_validates_input(async_client: AsyncClient):
    short = await async_client.post(
        "/api/v1/auth/register", json={"email": "short@example.com", "password": "abc"}
    )
    assert short.status_code == 422
    bad_email = await async_client.post(
        "/api/v1/auth/register", json={"email": "not-an-email", "password": "password123"}
    )
    assert bad_email.status_code == 422


@pytest.mark.asyncio
async def test_login_wrong_password_rejected(async_client: AsyncClient):
    await _register(async_client, "carol@example.com")
    bad = await async_client.post(
        "/api/v1/auth/login", json={"email": "carol@example.com", "password": "wrongpass1"}
    )
    assert bad.status_code == 401
    unknown = await async_client.post(
        "/api/v1/auth/login", json={"email": "nobody@example.com", "password": "password123"}
    )
    assert unknown.status_code == 401


@pytest.mark.asyncio
async def test_notes_require_auth(async_client: AsyncClient):
    assert (await async_client.get("/api/v1/notes")).status_code == 401
    assert (await async_client.get("/api/v1/notes/some-id")).status_code == 401
    fake = io.BytesIO(b"data")
    resp = await async_client.post("/api/v1/notes", files={"file": ("a.wav", fake, "audio/wav")})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_notes_isolated_per_user(async_client: AsyncClient):
    await _register(async_client, "dave@example.com")
    await _register(async_client, "erin@example.com")
    dave = await _login_headers(async_client, "dave@example.com")
    erin = await _login_headers(async_client, "erin@example.com")

    buf = io.BytesIO(b"RIFF" + b"\x00" * 100)
    up = await async_client.post(
        "/api/v1/notes",
        files={"file": ("d.wav", buf, "audio/wav")},
        data={"title": "Dave note"},
        headers=dave,
    )
    assert up.status_code == 202
    note_id = up.json()["id"]

    # Erin sees nothing of Dave's
    assert (await async_client.get(f"/api/v1/notes/{note_id}", headers=erin)).status_code == 404
    assert (await async_client.get(f"/api/v1/notes/{note_id}/status", headers=erin)).status_code == 404
    erin_list = await async_client.get("/api/v1/notes", headers=erin)
    assert erin_list.status_code == 200
    assert all(n["id"] != note_id for n in erin_list.json())
    dave_list = await async_client.get("/api/v1/notes", headers=dave)
    assert any(n["id"] == note_id for n in dave_list.json())


@pytest.mark.asyncio
async def test_legacy_ownerless_notes_hidden(async_client: AsyncClient, db_session: AsyncSession, auth_headers: dict):
    from app.models.audio_note import AudioNote, ProcessingStatus

    db_session.add(
        AudioNote(
            id="legacy-no-owner",
            title="Legacy",
            original_filename="l.wav",
            file_size_bytes=10,
            mime_type="audio/wav",
            storage_backend="local",
            storage_path="audio/legacy/l.wav",
            status=ProcessingStatus.COMPLETED,
            progress_percentage=100,
            current_step="done",
            language_code="en-IN",
        )
    )
    await db_session.commit()

    assert (await async_client.get("/api/v1/notes/legacy-no-owner", headers=auth_headers)).status_code == 404
    listing = await async_client.get("/api/v1/notes", headers=auth_headers)
    assert all(n["id"] != "legacy-no-owner" for n in listing.json())
