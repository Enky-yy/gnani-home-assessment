import type { ProcessingStatus } from "@/lib/api";

const LIVE: ProcessingStatus[] = ["PREPROCESSING", "TRANSCRIBING", "SUMMARIZING"];

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  const live = LIVE.includes(status);
  return (
    <span className="inline-flex shrink-0 items-center gap-1.5 font-mono text-xs text-mute">
      <span
        className={`inline-block h-1.5 w-1.5 rounded-full ${
          status === "FAILED" || live ? "bg-rec" : "bg-mute"
        } ${live ? "animate-pulse" : ""}`}
        aria-hidden
      />
      {status}
    </span>
  );
}

export function ProgressBar({ value, active }: { value: number; active?: boolean }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="h-0.5 w-full overflow-hidden rounded-full bg-white/20" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className={`h-full rounded-full transition-all ${active ? "bg-rec" : "bg-paper"}`} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded border border-rec/40 bg-rec/10 px-3 py-2 text-sm text-paper" role="alert">
      {message}
    </div>
  );
}
