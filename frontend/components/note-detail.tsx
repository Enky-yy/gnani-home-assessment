"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  TERMINAL_STATUSES,
  audioStreamUrl,
  deleteNote,
  formatBytes,
  formatDuration,
  getNote,
  getNoteStatus,
  renameNote,
  resummarizeNote,
  retryNote,
  type AudioNoteDetail,
} from "@/lib/api";
import { ErrorBanner, ProgressBar, StatusBadge } from "@/components/status";

export function NoteDetail({ id, initial }: { id: string; initial: AudioNoteDetail | null }) {
  const router = useRouter();
  const [note, setNote] = useState<AudioNoteDetail | null>(initial);
  const [loadError, setLoadError] = useState<string | null>(initial ? null : "Note not found.");
  const [actionError, setActionError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draftTitle, setDraftTitle] = useState(initial?.title ?? "");

  const refresh = useCallback(async () => {
    try {
      const full = await getNote(id);
      setNote(full);
      setDraftTitle((d) => (editing ? d : full.title));
      return full;
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load note.");
      return null;
    }
  }, [id, editing]);

  // Poll lightweight /status while processing, then fetch full detail once terminal.
  useEffect(() => {
    let timer: ReturnType<typeof setInterval> | null = null;
    async function tick() {
      try {
        const s = await getNoteStatus(id);
        setNote((prev) =>
          prev
            ? { ...prev, status: s.status, progress_percentage: s.progress_percentage, current_step: s.current_step, error_message: s.error_message }
            : prev
        );
        if (TERMINAL_STATUSES.includes(s.status)) {
          if (timer) clearInterval(timer);
          await refresh();
        }
      } catch {
        /* keep last state; next tick retries */
      }
    }
    if (!note || !TERMINAL_STATUSES.includes(note.status)) {
      timer = setInterval(tick, 2000);
      tick();
    }
    return () => {
      if (timer) clearInterval(timer);
    };
  }, [id, note?.status, refresh]);

  async function onRetry() {
    setBusy(true);
    setActionError(null);
    try {
      const updated = await retryNote(id);
      setNote(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onResummarize() {
    setBusy(true);
    setActionError(null);
    try {
      const updated = await resummarizeNote(id);
      setNote(updated);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Re-summarize failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onRename() {
    if (!draftTitle.trim()) {
      setActionError("Title cannot be empty.");
      return;
    }
    setBusy(true);
    setActionError(null);
    try {
      const updated = await renameNote(id, draftTitle.trim());
      setNote(updated);
      setEditing(false);
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Rename failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onDelete() {
    if (!confirm("Delete this note and its audio?")) return;
    setBusy(true);
    try {
      await deleteNote(id);
      router.push("/");
    } catch (err) {
      setActionError(err instanceof Error ? err.message : "Delete failed.");
      setBusy(false);
    }
  }

  if (!note) {
    return <ErrorBanner message={loadError ?? "Note not found."} />;
  }

  const processing = !TERMINAL_STATUSES.includes(note.status);

  return (
    <div className="grid gap-4">
      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <div className="flex flex-wrap items-center justify-between gap-3">
          {editing ? (
            <div className="flex gap-2">
              <input value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} className="rounded-md border px-3 py-1.5 text-sm" maxLength={255} />
              <button onClick={onRename} disabled={busy} className="rounded-md bg-zinc-900 px-3 py-1.5 text-sm text-white disabled:opacity-50">
                Save
              </button>
              <button onClick={() => setEditing(false)} className="rounded-md border px-3 py-1.5 text-sm">
                Cancel
              </button>
            </div>
          ) : (
            <h1 className="text-xl font-semibold">{note.title}</h1>
          )}
          <StatusBadge status={note.status} />
        </div>
        <p className="mt-1 text-xs text-zinc-500">
          {note.original_filename} · {formatBytes(note.file_size_bytes)} · {formatDuration(note.duration_seconds)} · {note.language_code}
        </p>
        {processing && (
          <div className="mt-3">
            <ProgressBar value={note.progress_percentage} />
            <p className="mt-1 text-sm text-zinc-600">
              {note.progress_percentage}% — {note.current_step}
            </p>
          </div>
        )}
        <ErrorBanner message={note.status === "FAILED" ? note.error_message : null} />
        <ErrorBanner message={actionError} />
        <div className="mt-3 flex flex-wrap gap-2 text-sm">
          {!editing && (
            <button onClick={() => setEditing(true)} className="rounded-md border px-3 py-1.5">
              Rename
            </button>
          )}
          {note.status === "FAILED" && (
            <button onClick={onRetry} disabled={busy} className="rounded-md bg-zinc-900 px-3 py-1.5 text-white disabled:opacity-50">
              {busy ? "Retrying…" : "Retry processing"}
            </button>
          )}
          {note.raw_transcript && (
            <button onClick={onResummarize} disabled={busy} className="rounded-md border px-3 py-1.5" title="Re-run only the LLM summary on the existing transcript (no re-transcription)">
              {busy ? "Summarizing…" : "Re-summarize"}
            </button>
          )}
          <button onClick={onDelete} disabled={busy} className="rounded-md border border-red-200 px-3 py-1.5 text-red-700">
            Delete
          </button>
        </div>
      </div>

      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Audio</h2>
        <audio controls src={audioStreamUrl(id)} className="mt-2 w-full" preload="metadata" />
        {note.asr_engine_used && <p className="mt-1 text-xs text-zinc-500">ASR: {note.asr_engine_used}{note.llm_model_used ? ` · Summary: ${note.llm_model_used}` : ""}</p>}
      </div>

      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Transcript</h2>
        {!note.raw_transcript ? (
          <p className="mt-2 text-sm text-zinc-600">{processing ? "Transcript is being generated…" : "No transcript yet."}</p>
        ) : (
          <>
            <p className="mt-2 whitespace-pre-wrap text-sm leading-relaxed">{note.raw_transcript}</p>
            {note.transcript_segments.length > 1 && (
              <ul className="mt-3 grid gap-2 border-t pt-3">
                {note.transcript_segments.map((s, i) => (
                  <li key={i} className="text-sm">
                    <span className="font-mono text-xs text-zinc-500">
                      [{s.start.toFixed(1)}s → {s.end.toFixed(1)}s]
                    </span>{" "}
                    {s.text}
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </div>

      <div className="rounded-lg border bg-white p-4 shadow-sm">
        <h2 className="font-semibold">Summary</h2>
        {!note.summary_tldr ? (
          <p className="mt-2 text-sm text-zinc-600">{processing ? "Summary will appear after transcription…" : "No summary yet."}</p>
        ) : (
          <div className="mt-2 grid gap-3 text-sm">
            <p className="leading-relaxed">{note.summary_tldr}</p>
            {note.summary_key_points.length > 0 && (
              <div>
                <h3 className="font-medium">Key points</h3>
                <ul className="mt-1 list-disc pl-5">
                  {note.summary_key_points.map((k, i) => (
                    <li key={i}>{k}</li>
                  ))}
                </ul>
              </div>
            )}
            {note.summary_action_items.length > 0 && (
              <div>
                <h3 className="font-medium">Action items</h3>
                <ul className="mt-1 list-disc pl-5">
                  {note.summary_action_items.map((a, i) => (
                    <li key={i}>{a}</li>
                  ))}
                </ul>
              </div>
            )}
            {note.summary_sentiment && <p className="text-xs text-zinc-500">Sentiment: {note.summary_sentiment}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
