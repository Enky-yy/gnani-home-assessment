# Audio Notes Platform — Backend API Service

Production-grade asynchronous audio processing backend built with **FastAPI**, **PostgreSQL**, **AWS S3**, **Gnani Voice AI ASR**, and **LLM Summarization**.

---

## 1. Architectural Highlights

- **Decoupled Asynchronous Processing**: Uploads return `202 Accepted` immediately. Heavy audio transcoding, chunking, Gnani ASR network requests, and LLM summarization run asynchronously in the background.
- **Handling Long Audio (≥ 2 minutes)**:
  - Clips $\le 60\text{s}$: Dispatched to Gnani's synchronous REST STT (`/stt/v3`).
  - Audio $> 60\text{s}$: Dynamically sliced into 45-second chunks with 1-second overlap using FFmpeg. Chunks are transcribed concurrently with bounded concurrency to respect API rate limits, then stitched with precise segment timestamps.
- **AWS S3 Storage Integration**: Audio streams are stored directly in AWS S3 buckets using `boto3`, generating presigned URLs for client streaming. Seamless fallback to local storage for zero-cloud offline development.
- **Visible Failure Tolerance**: Granular exception handling for corrupt files, missing audio streams, Gnani 429 rate limits, and network timeouts with exponential backoff and retry endpoints (`POST /notes/{id}/retry`).
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

## 4. Running Tests

```bash
# Run full pytest suite (audio inspection, chunking, API endpoints, e2e long audio)
pytest app/tests/ -v
```
