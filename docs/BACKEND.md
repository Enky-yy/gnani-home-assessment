# Audio Notes Platform — Backend API Service

Production-grade asynchronous audio processing backend built with **FastAPI**, **PostgreSQL**, **AWS S3**, **Gnani Voice AI ASR**, and **LLM Summarization**.

---

## 1. Architectural Highlights

- **Decoupled Asynchronous Processing**: Uploads return `202 Accepted` immediately. Heavy audio transcoding, chunking, Gnani ASR network requests, and LLM summarization run asynchronously in the background — via a durable Redis queue + `scripts/worker.py` when `REDIS_URL` is set, with automatic fallback to in-process FastAPI `BackgroundTasks` for zero-infra local dev.
- **Handling Long Audio (Gnani REST cap is 30s)**:
  - Clips `<= GNANI_MAX_REST_AUDIO_SECONDS` (25s default): Normalized first (see below), then a single Gnani synchronous REST STT (`/stt/v3`) call.
  - Audio `> 25s`: Dynamically sliced into 24-second chunks with 1-second overlap using FFmpeg. Chunks are transcribed serially (semaphore=1 + pacing sleep) to respect API rate limits, then stitched with precise segment timestamps.
- **ASR-Input Normalization**: Every clip is transcoded to clean 16kHz mono 16-bit PCM WAV before reaching Gnani, with a speech-band filter chain (80Hz highpass, 7.5kHz lowpass) plus EBU R128 loudness normalization — so quiet phone recordings and loud compressed rips (e.g. 48kHz stereo webm from YouTube) hit the engine at a consistent level. Chunked audio is already emitted normalized by the chunker and skips the second pass.
- **Seam-Dedup Stitching**: Consecutive chunks share ~1s of audio, so the full transcript is stitched with word-level suffix/prefix overlap merging (case/punctuation-insensitive, minimum 3 words to avoid false merges on bigrams like "of the") instead of naive joining. Per-chunk segments keep their original text and timestamps.
- **AWS S3 Storage Integration**: Audio streams are stored directly in AWS S3 buckets using `boto3`, with seamless fallback to local storage for zero-cloud offline development. Playback is always backend-streamed (temp file with Range/seek, deleted after serving) — no presigned URLs reach the browser. Local layout preserves partitioning (`<base>/audio/<note_id>/<filename>`) with traversal protection, legacy flat-file fallback, empty-dir cleanup on delete, and note-scoped playback URLs (`/api/v1/notes/{id}/audio`).
- **Upload Guardrails**: Extension allowlist + `MAX_UPLOAD_SIZE_MB` (default 500MB ≈ 8+ hours of MP3, enforced pre- and post-save with `413` + orphan cleanup) matches Nginx `client_max_body_size 500M` (300s proxy timeouts for slow links).
- **Visible Failure Tolerance**: Granular exception handling for corrupt files, missing audio streams, Gnani 429 rate limits, and network timeouts with exponential backoff and retry endpoints (`POST /notes/{id}/retry`). Auth failures (401/403, e.g. expired keys) are never retried and surface visibly: a single clip fails the note to `FAILED`, while chunked audio fails only if *all* chunks error — partial chunk failures return the surviving text. The LLM summarizer fails over across every keyed provider (configured first), ignores `.env.example`-style placeholder keys entirely, and degrades to a labeled rule-based extractive summary only as a last resort. Saved transcripts can be re-summarized without re-transcribing (`POST /notes/{id}/summarize`). Every successful Gnani call logs its `request_id` for support correlation.
- **PostgreSQL State Machine**: Tracks status through `UPLOADED` $\rightarrow$ `PREPROCESSING` $\rightarrow$ `TRANSCRIBING` $\rightarrow$ `SUMMARIZING` $\rightarrow$ `COMPLETED` / `FAILED`.
- **Auth & Private Notes**: Email + password with bcrypt hashing; 7-day JWT bearer tokens (`Authorization: Bearer`). Every note carries `owner_id` and all note endpoints are scoped to the caller (cross-user access returns 404; legacy ownerless rows are hidden). Wrapper `init_db` migrates pre-auth databases idempotently.

---

## 2. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/auth/register` | Create an account (email + password, 8+ chars). |
| `POST` | `/api/v1/auth/login` | Log in, receive a 7-day JWT bearer token. |
| `GET` | `/api/v1/auth/me` | Current user profile (requires token). |
| `POST` | `/api/v1/notes` | Upload audio file (`multipart/form-data`) & enqueue processing. |
| `GET` | `/api/v1/notes` | List past uploads (supports search `?q=` across titles & transcripts). |
| `GET` | `/api/v1/notes/{id}` | Get full note details, transcript segments, and LLM summary. |
| `GET` | `/api/v1/notes/{id}/status`| Fast polling endpoint for real-time progress percentage & current step. |
| `GET` | `/api/v1/notes/{id}/audio` | Stream audio bytes (local file or S3 object via temp file; Range/seek supported). |
| `POST` | `/api/v1/notes/{id}/retry` | Re-trigger processing on a failed or stuck note. |
| `POST` | `/api/v1/notes/{id}/summarize` | Re-run LLM summarization on the stored transcript (no re-transcription). |
| `PATCH`| `/api/v1/notes/{id}/title` | Rename an audio note title. |
| `DELETE`| `/api/v1/notes/{id}` | Delete note and purge audio blob from S3 storage. |
| `GET` | `/api/v1/health` | Deep diagnostic health check (DB, S3, Gnani, LLM status). |

---

## 3. Running Locally

### Prerequisites
- Python 3.10+
- FFmpeg (`sudo apt install ffmpeg` or `brew install ffmpeg`)

### Setup & Run
```bash
# 1. Create virtual environment & install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Configure environment
cp .env.example .env
# Edit .env with your AWS S3 and Gnani credentials

# 3. Seed demo data (public demo login + 2 sample notes, idempotent)
python scripts/seed_demo_data.py
# Reviewers log in as demo@example.com / demo1234 — no registration needed.

# 4. Start development server
uvicorn app.main:app --reload --port 8000
```
- Interactive Swagger API Docs: `http://localhost:8000/docs`
- Deep Health Check: `http://localhost:8000/api/v1/health`

---

# 4. Background worker (durable Redis queue)

```bash
# Terminal 1: API (in-process BackgroundTasks fallback when REDIS_URL is empty)
uvicorn app.main:app --reload --port 8000

# Terminal 2: durable worker (requires REDIS_URL + `redis` package)
export REDIS_URL=redis://localhost:6379/0
python scripts/worker.py
```
- With `REDIS_URL` set, `POST /notes` and `POST /notes/{id}/retry` push to Redis list `audio_notes:jobs`; `scripts/worker.py` pops and runs `process_audio_note_job`. Survives API restarts, unlike pure `BackgroundTasks`. The worker's Redis `socket_timeout` is set above the `BLPOP` blocking timeout so idle loops wait cleanly instead of erroring.
- `docker compose up` runs this worker automatically as the `worker` service (shares `backend_uploads` volume + `DATABASE_URL`/`REDIS_URL`).
- Health endpoint reports queue status: `GET /api/v1/health` -> `queue.backend: redis|background-tasks`, `pending_jobs`.

---

## 5. Running Tests

```bash
# Run full pytest suite — 32 tests: auth (register/login/isolation), stream
# auth gates, audio inspection, 16kHz normalization, overlap-merge stitching,
# chunk all-fail vs partial-fail, LLM failover + placeholder guard,
# resummarize endpoint, API endpoints, e2e long audio, summarizer
pytest app/tests/ -v
```

---

## 6. Deployment

Live at `https://gnani.harsh-shah.me` via Cloudflare Tunnel (see `DEPLOY.md`):
outbound-only `cloudflared` container routes the domain to the internal
nginx (`/api/*` → backend, `/` → frontend). No public ports required;
TLS terminates at the Cloudflare edge.
