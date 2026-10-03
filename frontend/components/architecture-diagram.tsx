// Static, code-drawn architecture diagrams. No images, no libraries:
// boxes + labeled arrows in the site's own mono type.

function Node({ title, sub }: { title: string; sub?: string }) {
  return (
    <div className="rounded border border-white/20 bg-void px-3 py-2 text-center">
      <div className="font-mono text-xs font-medium text-paper">{title}</div>
      {sub && <div className="mt-0.5 font-mono text-[11px] text-mute">{sub}</div>}
    </div>
  );
}

function Arrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 py-1" aria-hidden>
      <span className="font-mono text-xs text-mute">↓</span>
      {label && <span className="font-mono text-[11px] text-mute">{label}</span>}
    </div>
  );
}

function BranchArrow({ label }: { label?: string }) {
  return (
    <div className="flex flex-col items-center gap-0.5 py-1" aria-hidden>
      <span className="font-mono text-xs text-mute">↙&nbsp;&nbsp;↘</span>
      {label && <span className="font-mono text-[11px] text-mute">{label}</span>}
    </div>
  );
}

export function SystemDiagram() {
  return (
    <div className="grid gap-0" role="img" aria-label="System request-flow diagram">
      <Node title="Browser" sub="Next.js UI · JWT in localStorage" />
      <Arrow label="https · gnani.harsh-shah.me" />
      <Node title="Cloudflare Tunnel" sub="outbound-only · TLS at edge" />
      <Arrow label="http://nginx:80 (compose net)" />
      <Node title="nginx (internal)" sub="/api/* → backend · / → frontend · 500M" />
      <div className="grid grid-cols-2 gap-3 pt-2">
        <div className="grid gap-0">
          <Node title="frontend :3000" sub="upload · list · detail · /login" />
        </div>
        <div className="grid gap-0">
          <Node title="backend :8000" sub="auth · notes · health · audio" />
        </div>
      </div>
      <BranchArrow label="jobs / state / files" />
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Node title="worker" sub="pops audio_notes:jobs" />
        <Node title="Postgres" sub="users · notes · status" />
        <Node title="Redis" sub="durable job queue" />
        <Node title="S3 / local" sub="audio/<id>/<file>" />
      </div>
      <Arrow label="HTTPS APIs" />
      <div className="grid grid-cols-2 gap-3">
        <Node title="Gnani Prisma v2.5" sub="STT REST /stt/v3" />
        <Node title="Groq / Gemini" sub="LangChain summary · failover" />
      </div>
    </div>
  );
}

export function PipelineDiagram() {
  return (
    <div className="grid gap-0" role="img" aria-label="Transcription pipeline diagram">
      <Node title="202 Accepted" sub="row in UPLOADED · id enqueued" />
      <Arrow label="worker pops id" />
      <Node title="download + ffprobe" sub="scratch dir · PREPROCESSING" />
      <Arrow label="normalize" />
      <Node title="16kHz mono + speech band + loudnorm" sub="TRANSCRIBING" />
      <BranchArrow label="duration ≤ 25s ?" />
      <div className="grid grid-cols-2 gap-3">
        <Node title="single REST call" sub="one transcript" />
        <Node title="24s chunks · 1s overlap" sub="serial · stitched · deduped" />
      </div>
      <Arrow label="LangChain" />
      <Node title="TL;DR · key points · actions · sentiment" sub="SUMMARIZING → COMPLETED" />
    </div>
  );
}
