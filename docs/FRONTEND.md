# Frontend — Next.js 14 App Router + Tailwind

## Routes

| Route | Purpose |
|---|---|
| `/` | Upload dropzone (extension + 500MB client checks) + private history list |
| `/notes/[id]` | Audio player, live progress, transcript segments, summary, rename / retry / re-summarize / delete |
| `/login` | Login / register toggle (min 8-char password); shows public demo credentials (`demo@example.com` / `demo1234`) |
| `/architecture` | In-app architecture writeup with repo link |

## Data fetching: two contexts

- **Browser:** same-origin relative `/api/*` through nginx (`lib/api.ts`
  `url()` with empty `NEXT_PUBLIC_API_URL`).
- **Server pre-render:** Node `fetch` needs absolute URLs, so server components
  use `BACKEND_INTERNAL_URL` (`http://backend:8000` in compose, localhost
  fallback for local dev). The home/detail pages are client components that
  fetch on mount instead.

## Auth flow (`lib/api.ts`, `components/auth-nav.tsx`)

- JWT in `localStorage` (`audio_notes_token`), sent as
  `Authorization: Bearer` on every note call; typed `ApiError` carries status.
- No token or any 401 → redirect `/login` (and token cleared). Header nav
  re-checks `/me` on every navigation so login/logout reflect instantly.
- `<audio>` can't send headers, so playback loads via authenticated
  `fetch` → blob object URL (`fetchAudioBlobUrl`), revoked on unmount.
- Re-summarize is a single synchronous LLM call: indeterminate sliding bar
  (`globals.css`) while it runs; the determinate % bar is reserved for the
  multi-step transcription pipeline (`GET /status` polled every 2s).

## Env vars

| Var | Purpose |
|---|---|
| `NEXT_PUBLIC_API_URL` | Absolute API base for the browser (empty = same-origin; compose default) |
| `BACKEND_INTERNAL_URL` | Absolute API base for server pre-render (`http://backend:8000` in compose) |
| `BACKEND_INTERNAL_URL` / dev | `npm run dev` against local backend: `NEXT_PUBLIC_API_URL=http://localhost:8000` |

## Local dev

```bash
cd frontend
npm install
NEXT_PUBLIC_API_URL=http://localhost:8000 npm run dev -- --port 3100
```

Production builds to standalone output (`Dockerfile`) served on `:3000`.
