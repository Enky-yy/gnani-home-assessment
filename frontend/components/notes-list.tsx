import Link from "next/link";
import { formatBytes, formatDuration, type AudioNoteListItem } from "@/lib/api";
import { StatusBadge, ProgressBar } from "./status";

export function NotesList({ notes }: { notes: AudioNoteListItem[] }) {
  if (notes.length === 0) {
    return <p className="mt-6 text-sm text-mute">No uploads yet. Upload your first recording above.</p>;
  }
  return (
    <ul className="mt-2 divide-y divide-white/10 border-y border-white/10">
      {notes.map((n) => (
        <li key={n.id} className="py-5">
          <div className="flex items-baseline justify-between gap-3">
            <Link href={`/notes/${n.id}`} className="text-lg font-medium tracking-tight text-paper hover:underline">
              {n.title}
            </Link>
            <StatusBadge status={n.status} />
          </div>
          <p className="mt-1 font-mono text-xs text-mute">
            {n.original_filename} · {formatBytes(n.file_size_bytes)} · {formatDuration(n.duration_seconds)}
          </p>
          {n.status !== "COMPLETED" && n.status !== "FAILED" && (
            <div className="mt-3 max-w-md">
              <ProgressBar value={n.progress_percentage} active />
              <p className="mt-1.5 text-sm text-mute">{n.current_step}</p>
            </div>
          )}
          {n.status === "FAILED" && n.error_message && (
            <p className="mt-2 text-sm text-rec">{n.error_message}</p>
          )}
          {n.summary_tldr && <p className="mt-2 line-clamp-2 max-w-2xl text-sm leading-relaxed text-paper/80">{n.summary_tldr}</p>}
        </li>
      ))}
    </ul>
  );
}
