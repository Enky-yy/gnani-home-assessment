# Audio Notes Platform

Upload audio → Gnani ASR transcript → LLM summary. Live at
**https://gnani.harsh-shah.me**.

Gnani internship take-home: Next.js frontend, FastAPI backend, PostgreSQL,
storage bucket (S3/local), Redis background jobs. Past uploads are listed and
reopenable; long audio (2min+) is chunked with visible progress and failure
states.

## Quickstart

```bash
# 1. Configure secrets (never committed)
cp backend/.env.example backend/.env   # Gnani + LLM + S3 keys
# 2. Run everything
sudo docker compose up --build -d
# 3. Open http://localhost (or the public domain, see DEPLOY.md)
```

## Docs (all in `docs/`)

- `docs/ARCHITECTURE.md` — full technical writeup (also served in-app at `/architecture`).
- `docs/BACKEND.md` — API reference, local dev, worker, tests.
- `docs/FRONTEND.md` — routes, data fetching, auth flow, env vars.
- `docs/DEPLOY.md` — public deployment via Cloudflare Tunnel, secrets, runbook.

## Tests

```bash
cd backend && .venv/bin/python -m pytest app/tests/ -v   # 24 tests
```
