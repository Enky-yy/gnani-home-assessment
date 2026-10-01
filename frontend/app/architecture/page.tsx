export default function ArchitecturePage() {
  return (
    <article className="grid gap-6 rounded-lg border bg-white p-6 shadow-sm">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Architecture</h1>
        <p className="mt-1 text-sm text-zinc-600">
          How the Audio Notes Platform turns an upload into a transcript and summary. GitHub:{" "}
          <a className="underline" href="https://github.com/Enky-yy/gnani-home-assessment">
            Enky-yy/gnani-home-assessment
          </a>
        </p>
      </div>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">Flow from upload to transcript</h2>
        <ol className="list-decimal pl-5">
          <li>
            Browser posts <code>multipart/form-data</code> to <code>POST /api/v1/notes</code> through nginx (500MB limit, ~8+ hours of audio). The backend
            validates extension and size, stores the stream, inserts a PostgreSQL row in <code>UPLOADED</code>, and returns 202 with the note id.
          </li>
          <li>
            The note id is pushed to the Redis list <code>audio_notes:jobs</code>. The <code>worker</code> service pops it and runs{" "}
            <code>process_audio_note_job</code>; without <code>REDIS_URL</code> the API falls back to in-process BackgroundTasks.
          </li>
          <li>
            The worker downloads the audio to scratch space, runs ffprobe validation, normalizes to 16kHz mono with speech-band filtering and
            loudness normalization, then Gnani ASR: single REST call when duration ≤ 25s, otherwise 24s overlapping chunks transcribed serially,
            stitched with overlap-dedup and timestamps. Each successful Gnani call logs its <code>request_id</code>.
          </li>
          <li>
            The transcript goes through a LangChain summarization chain (Gemini/Groq/OpenAI, extractive fallback with no keys) producing TL;DR,
            key points, action items, and sentiment. Results persist to Postgres and the note flips to <code>COMPLETED</code>; any failure flips to{" "}
            <code>FAILED</code> with a visible error and retry endpoint.
          </li>
          <li>
            The frontend polls lightweight <code>GET /api/v1/notes/{"{id}"}/status</code> every 2s for progress, then loads the full note. Audio plays
            from <code>GET /api/v1/notes/{"{id}"}/audio</code> (S3 presigned redirect or local file stream).
          </li>
        </ol>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">Where files live</h2>
        <p>
          Production uses AWS S3 via boto3 under keys <code>audio/{"<note_id>"}/{"<filename>"}</code> with presigned playback URLs. Local development uses
          the same key layout under <code>/app/uploads</code> (shared <code>backend_uploads</code> volume between API and worker), with traversal
          protection and cleanup of empty note folders on delete.
        </p>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">How long audio is handled</h2>
        <p>
          Gnani REST rejects audio over 30s, so the backend caps REST at 25s (<code>GNANI_MAX_REST_AUDIO_SECONDS</code>) and slices anything longer into
          24s FFmpeg chunks with 1s overlap at 16kHz mono. Chunks run serially with pacing to avoid 429 rate limits, each with exponential-backoff
          retries; the shared ~1s overlap is collapsed with word-level suffix/prefix merging so seams don&apos;t duplicate phrases. Segments are sorted
          by start time for the timestamped view. A 2 minute recording becomes ~6 chunks and never blocks the upload request.
        </p>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">Failure handling and fallbacks</h2>
        <ul className="list-disc pl-5">
          <li>Corrupt or empty files fail fast to <code>FAILED</code> with the ffprobe reason shown and a Retry button.</li>
          <li>Expired/revoked Gnani keys (401/403) are never retried: a short clip fails the note visibly, while chunked audio fails only if every chunk
          errors — one bad chunk still leaves the surviving transcript.</li>
          <li>An expired LLM key degrades to a rule-based extractive summary, labeled <code>langchain-extractive-fallback</code> next to the ASR engine name.</li>
          <li>With no Gnani key at all the backend runs in clearly-labeled demo-simulation mode (<code>/api/v1/health</code> reports it) for offline development.</li>
        </ul>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">How the frontend reaches the backend</h2>
        <p>
          In the browser, all API calls use same-origin relative <code>/api/*</code> URLs through nginx, which proxies them to the backend. Page
          pre-rendering happens on the Next.js server, where relative URLs don&apos;t resolve — so server components call the backend directly via{" "}
          <code>BACKEND_INTERNAL_URL</code> (<code>http://backend:8000</code> in compose, localhost fallback for local dev).
        </p>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">Synchronous vs background</h2>
        <ul className="list-disc pl-5">
          <li>Synchronous: extension/size validation, storage write, DB insert, 202 response, status polling reads, audio streaming.</li>
          <li>Background: storage download, ffprobe, Gnani chunking/transcription, LLM summarization, final DB write, scratch cleanup.</li>
        </ul>
      </section>

      <section className="grid gap-2 text-sm leading-relaxed">
        <h2 className="text-lg font-semibold">With more time</h2>
        <ul className="list-disc pl-5">
          <li>Replace polling with server-sent events for progress.</li>
          <li>Add speaker diarization display and word-level timestamps.</li>
          <li>Add auth, per-user note scoping, and full-text search ranking.</li>
          <li>Move chunk transcription to parallel workers with a token bucket once Gnani quotas allow.</li>
          <li>Evaluate Gnani Batch STT for long files: one full-context pass with zero seams, at the cost of async job polling and no gu-IN/pa-IN support.</li>
        </ul>
      </section>
    </article>
  );
}
