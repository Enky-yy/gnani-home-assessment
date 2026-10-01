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
- **AWS S3 Storage Integration**: Audio streams are stored directly in AWS S3 buckets using `boto3`, generating presigned URLs for client streaming. Seamless fallback to local storage for zero-cloud offline development. Local layout preserves partitioning (`<base>/audio/<note_id>/<filename>`) with traversal protection, legacy flat-file fallback, and empty-dir cleanup on delete. Local playback URLs are note-scoped (`/api/v1/notes/{id}/audio`).
- **Upload Guardrails**: Extension allowlist + `MAX_UPLOAD_SIZE_MB` (default 500MB ≈ 8+ hours of MP3, enforced pre- and post-save with `413` + orphan cleanup) matches Nginx `client_max_body_size 500M` (300s proxy timeouts for slow links).
- **Visible Failure Tolerance**: Granular exception handling for corrupt files, missing audio streams, Gnani 429 rate limits, and network timeouts with exponential backoff and retry endpoints (`POST /notes/{id}/retry`). Auth failures (401/403, e.g. expired keys) are never retried and surface visibly: a single clip fails the note to `FAILED`, while chunked audio fails only if *all* chunks error — partial chunk failures return the surviving text. An expired LLM key degrades gracefully to the rule-based extractive summary, labeled `langchain-extractive-fallback` in `llm_model_used`. Every successful Gnani call logs its `request_id` for support correlation.
- **PostgreSQL State Machine**: Tracks status through `UPLOADED` $\rightarrow$ `PREPROCESSING` $\rightarrow$ `TRANSCRIBING` $\rightarrow$ `SUMMARIZING` $\rightarrow$ `COMPLETED` / `FAILED`.

---

## 2. API Endpoints Reference

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/v1/notes` | Upload audio file (`multipart/form-data`) & enqueue processing. |
| `GET` | `/api/v1/notes` | List past uploads (supports search `?q=` across titles & transcripts). |
| `GET` | `/api/v1/notes/{id}` | Get full note details, transcript segments, and LLM summary. |
| `GET` | `/api/v1/notes/{id}/status`| Fast polling endpoint for real-time progress percentage & current step. |
| `GET` | `/api/v1/notes/{id}/audio` | Stream audio file directly or redirect to presigned S3 URL. |
| `POST` | `/api/v1/notes/{id}/retry` | Re-trigger processing on a failed or stuck note. |
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

# 3. Seed demo data (optional, for immediate preview)
python scripts/seed_demo_data.py

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
# Run full pytest suite — 18 tests: audio inspection, 16kHz normalization,
# overlap-merge stitching, chunk all-fail vs partial-fail behavior,
# API endpoints, e2e long audio, summarizer
pytest app/tests/ -v
```
