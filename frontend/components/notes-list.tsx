import Link from "next/link";
import { formatBytes, formatDuration, type AudioNoteListItem } from "@/lib/api";
import { StatusBadge, ProgressBar } from "./status";

export function NotesList({ notes }: { notes: AudioNoteListItem[] }) {
  if (notes.length === 0) {
    return <p className="mt-4 text-sm text-zinc-600">No uploads yet. Upload your first recording above.</p>;
  }
  return (
    <ul className="mt-4 grid gap-3">
      {notes.map((n) => (
        <li key={n.id} className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between gap-3">
            <Link href={`/notes/${n.id}`} className="font-medium hover:underline">
              {n.title}
            </Link>
            <StatusBadge status={n.status} />
          </div>
          <p className="mt-1 text-xs text-zinc-500">
            {n.original_filename} · {formatBytes(n.file_size_bytes)} · {formatDuration(n.duration_seconds)}
          </p>
          {n.status !== "COMPLETED" && n.status !== "FAILED" && (
            <div className="mt-2">
              <ProgressBar value={n.progress_percentage} />
              <p className="mt-1 text-xs text-zinc-600">{n.current_step}</p>
            </div>
          )}
          {n.status === "FAILED" && n.error_message && (
            <p className="mt-2 text-xs text-red-700">{n.error_message}</p>
          )}
          {n.summary_tldr && <p className="mt-2 line-clamp-2 text-sm text-zinc-700">{n.summary_tldr}</p>}
        </li>
      ))}
    </ul>
  );
}
