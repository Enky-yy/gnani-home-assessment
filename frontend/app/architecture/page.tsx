export default function ArchitecturePage() {
  return (
    <article className="grid gap-10">
      <div>
        <h1 className="text-3xl font-semibold tracking-tight text-paper">Architecture</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-mute">
          How the Audio Notes Platform turns an upload into a transcript and summary. GitHub:{" "}
          <a className="text-paper underline decoration-white/30 underline-offset-4 hover:decoration-paper" href="https://github.com/Enky-yy/gnani-home-assessment">
            Enky-yy/gnani-home-assessment
          </a>
        </p>
      </div>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Flow from upload to transcript</h2>
        <ol className="grid list-decimal gap-2 pl-5">
          <li>
            Browser posts <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">multipart/form-data</code> to <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">POST /api/v1/notes</code> through nginx (500MB limit, ~8+ hours of audio). The backend
            validates extension and size, stores the stream, inserts a PostgreSQL row in <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">UPLOADED</code>, and returns 202 with the note id.
            All note endpoints require login (email + password, JWT bearer token) and notes are private per account. Reviewers can skip
            registration with the demo account (<code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">demo@example.com</code> / <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">demo1234</code>, shown on the login page) which
            comes with two completed sample notes.
          </li>
          <li>
            The note id is pushed to the Redis list <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">audio_notes:jobs</code>. The <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">worker</code> service pops it and runs{" "}
            <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">process_audio_note_job</code>; without <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">REDIS_URL</code> the API falls back to in-process BackgroundTasks.
          </li>
          <li>
            The worker downloads the audio to scratch space, runs ffprobe validation, normalizes to 16kHz mono with speech-band filtering and
            loudness normalization, then Gnani ASR: single REST call when duration ≤ 25s, otherwise 24s overlapping chunks transcribed serially,
            stitched with overlap-dedup and timestamps. Each successful Gnani call logs its <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">request_id</code>.
          </li>
          <li>
            The transcript goes through a LangChain summarization chain with provider failover: the configured provider first (currently Groq), then any
            other keyed provider if one fails — so an expired key or exhausted quota no longer kills the summary. <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">.env.example</code>-style
            placeholder keys are never tried or reported as active. If every provider fails, a labeled rule-based extractive summary is stored instead
            of nothing. Results persist to Postgres and the note flips to <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">COMPLETED</code>; any failure flips to <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">FAILED</code> with a
            visible error and retry endpoint. A saved transcript can be re-summarized any time via <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">POST /api/v1/notes/{"{id}"}/summarize</code>{" "}
            without re-transcribing.
          </li>
          <li>
            The frontend polls lightweight <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">GET /api/v1/notes/{"{id}"}/status</code> every 2s for progress, then loads the full note. Audio plays
            from <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">GET /api/v1/notes/{"{id}"}/audio</code> (S3 presigned redirect or local file stream).
          </li>
        </ol>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Where files live</h2>
        <p>
          Production uses AWS S3 via boto3 under keys <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">audio/{"<note_id>"}/{"<filename>"}</code> with presigned playback URLs. Local development uses
          the same key layout under <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">/app/uploads</code> (shared <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">backend_uploads</code> volume between API and worker), with traversal
          protection and cleanup of empty note folders on delete.
        </p>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">How long audio is handled</h2>
        <p>
          Gnani REST rejects audio over 30s, so the backend caps REST at 25s (<code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">GNANI_MAX_REST_AUDIO_SECONDS</code>) and slices anything longer into
          24s FFmpeg chunks with 1s overlap at 16kHz mono. Chunks run serially with pacing to avoid 429 rate limits, each with exponential-backoff
          retries; the shared ~1s overlap is collapsed with word-level suffix/prefix merging so seams don&apos;t duplicate phrases. Segments are sorted
          by start time for the timestamped view. A 2 minute recording becomes ~6 chunks and never blocks the upload request.
        </p>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Failure handling and fallbacks</h2>
        <ul className="grid list-disc gap-2 pl-5">
          <li>Corrupt or empty files fail fast to <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">FAILED</code> with the ffprobe reason shown and a Retry button.</li>
          <li>Expired/revoked Gnani keys (401/403) are never retried: a short clip fails the note visibly, while chunked audio fails only if every chunk
          errors — one bad chunk still leaves the surviving transcript.</li>
          <li>An expired LLM key degrades to a rule-based extractive summary, labeled <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">langchain-extractive-fallback</code> next to the ASR engine name.</li>
          <li>With no Gnani key at all the backend runs in clearly-labeled demo-simulation mode (<code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">/api/v1/health</code> reports it) for offline development.</li>
        </ul>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">How the frontend reaches the backend</h2>
        <p>
          In the browser, all API calls use same-origin relative <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">/api/*</code> URLs through nginx, which proxies them to the backend. Page
          pre-rendering happens on the Next.js server, where relative URLs don&apos;t resolve — so server components call the backend directly via{" "}
          <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">BACKEND_INTERNAL_URL</code> (<code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">http://backend:8000</code> in compose, localhost fallback for local dev).
        </p>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Synchronous vs background</h2>
        <ul className="grid list-disc gap-2 pl-5">
          <li>Synchronous: extension/size validation, storage write, DB insert, 202 response, status polling reads, audio streaming.</li>
          <li>Background: storage download, ffprobe, Gnani chunking/transcription, LLM summarization, final DB write, scratch cleanup.</li>
        </ul>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Deployment</h2>
        <p>
          The app is live at <a className="underline" href="https://gnani.harsh-shah.me">https://gnani.harsh-shah.me</a> from a single{" "}
          <code className="rounded bg-white/10 px-1 py-0.5 font-mono text-[13px] text-paper">docker compose up</code> (Next.js, FastAPI, worker, Postgres, Redis, internal nginx, Cloudflare Tunnel). The host runs Docker at home
          with no reachable public ports, so a Cloudflare Tunnel container dials out and routes the domain to the internal nginx — TLS terminates at
          Cloudflare&apos;s edge, and no firewall rules or port forwarding were needed. Uploads up to 500MB (~8+ hours of audio) are accepted end to end.
        </p>
      </section>

      <section className="grid max-w-2xl gap-3 border-t border-white/10 pt-6 text-sm leading-relaxed text-paper/85">
        <h2 className="text-lg font-semibold tracking-tight text-paper">With more time</h2>
        <ul className="grid list-disc gap-2 pl-5">
          <li>Replace polling with server-sent events for progress.</li>
          <li>Add speaker diarization display and word-level timestamps.</li>
          <li>Add full-text search ranking across titles and transcripts.</li>
          <li>Move chunk transcription to parallel workers with a token bucket once Gnani quotas allow.</li>
          <li>Evaluate Gnani Batch STT for long files: one full-context pass with zero seams, at the cost of async job polling and no gu-IN/pa-IN support.</li>
        </ul>
      </section>
    </article>
  );
}
