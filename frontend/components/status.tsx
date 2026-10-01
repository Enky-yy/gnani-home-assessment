import type { ProcessingStatus } from "@/lib/api";

const STYLES: Record<ProcessingStatus, string> = {
  UPLOADED: "bg-zinc-200 text-zinc-700",
  PREPROCESSING: "bg-blue-100 text-blue-800",
  TRANSCRIBING: "bg-amber-100 text-amber-800",
  SUMMARIZING: "bg-violet-100 text-violet-800",
  COMPLETED: "bg-green-100 text-green-800",
  FAILED: "bg-red-100 text-red-800",
};

export function StatusBadge({ status }: { status: ProcessingStatus }) {
  return (
    <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${STYLES[status]}`}>
      {status}
    </span>
  );
}

export function ProgressBar({ value }: { value: number }) {
  const pct = Math.max(0, Math.min(100, value));
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-zinc-200" role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-zinc-900 transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function ErrorBanner({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
      {message}
    </div>
  );
}
