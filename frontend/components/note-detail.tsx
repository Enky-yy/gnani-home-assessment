"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  TERMINAL_STATUSES,
  deleteNote,
  fetchAudioBlobUrl,
  formatBytes,
  formatDuration,
  getNote,
  isUnauthorized,
  logout,
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
  const [summarizing, setSummarizing] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioError, setAudioError] = useState<string | null>(null);
  const [audioFellBack, setAudioFellBack] = useState(false);
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
      if (isUnauthorized(err)) {
        logout();
        router.push("/login");
        return;
      }
      setActionError(err instanceof Error ? err.message : "Retry failed.");
    } finally {
      setBusy(false);
    }
  }

  async function onResummarize() {
    setBusy(true);
    setSummarizing(true);
    setActionError(null);
    try {
      const updated = await resummarizeNote(id);
      setNote(updated);
    } catch (err) {
      if (isUnauthorized(err)) {
        logout();
        router.push("/login");
        return;
      }
      setActionError(err instanceof Error ? err.message : "Re-summarize failed.");
    } finally {
      setBusy(false);
      setSummarizing(false);
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

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setAudioUrl(null);
    setAudioError(null);

    // One uniform flow for every backend: authenticated fetch of /audio
    // (the backend streams S3 bytes itself, so no presigned URL ever
    // reaches the browser), then blob playback.
    async function load() {
      try {
        const blobUrl = await fetchAudioBlobUrl(id);
        objectUrl = blobUrl;
        if (!cancelled) setAudioUrl(blobUrl);
      } catch (err) {
        if (cancelled) return;
        if (isUnauthorized(err)) {
          logout();
          router.push("/login");
          return;
        }
        // Seeded demo notes reference external sample audio — play it directly.
        if (note?.audio_url?.startsWith("http")) {
          setAudioUrl(note.audio_url);
          return;
        }
        setAudioError(err instanceof Error ? err.message : "Could not load audio.");
      }
    }
    load();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  if (!note) {
    return <ErrorBanner message={loadError ?? "Note not found."} />;
  }

  const processing = !TERMINAL_STATUSES.includes(note.status);

  return (
    <div className="grid gap-10">
      <section>
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          {editing ? (
            <div className="flex gap-2">
              <input value={draftTitle} onChange={(e) => setDraftTitle(e.target.value)} className="rounded border border-white/15 bg-void px-3 py-1.5 text-sm text-paper" maxLength={255} />
              <button onClick={onRename} disabled={busy} className="rounded bg-paper px-3 py-1.5 text-sm font-medium text-void disabled:opacity-40">
                Save
              </button>
              <button onClick={() => setEditing(false)} className="rounded border border-white/20 px-3 py-1.5 text-sm text-paper">
                Cancel
              </button>
            </div>
          ) : (
            <h1 className="text-2xl font-semibold tracking-tight text-paper">{note.title}</h1>
          )}
          <StatusBadge status={note.status} />
        </div>
        <p className="mt-1 font-mono text-xs text-mute">
          {note.original_filename} · {formatBytes(note.file_size_bytes)} · {formatDuration(note.duration_seconds)} · {note.language_code}
        </p>
        {processing && (
          <div className="mt-4 max-w-md">
            <ProgressBar value={note.progress_percentage} active />
            <p className="mt-1.5 font-mono text-xs text-mute">
              {note.progress_percentage}% — {note.current_step}
            </p>
          </div>
        )}
        <div className="mt-3 grid gap-2">
          <ErrorBanner message={note.status === "FAILED" ? note.error_message : null} />
          <ErrorBanner message={actionError} />
        </div>
        <div className="mt-4 flex flex-wrap gap-2 text-sm">
          {!editing && (
            <button onClick={() => setEditing(true)} className="rounded border border-white/20 px-3 py-1.5 text-paper hover:border-paper">
              Rename
            </button>
          )}
          {note.status === "FAILED" && (
            <button onClick={onRetry} disabled={busy} className="rounded bg-paper px-3 py-1.5 font-medium text-void disabled:opacity-40">
              {busy ? "Retrying…" : "Retry processing"}
            </button>
          )}
          {note.raw_transcript && (
            <button onClick={onResummarize} disabled={busy} className="rounded border border-white/20 px-3 py-1.5 text-paper hover:border-paper disabled:opacity-40" title="Re-run only the LLM summary on the existing transcript (no re-transcription)">
              {busy ? "Summarizing…" : "Re-summarize"}
            </button>
          )}
          <button onClick={onDelete} disabled={busy} className="rounded border border-rec/50 px-3 py-1.5 text-rec disabled:opacity-40">
            Delete
          </button>
        </div>
      </section>

      <section className="border-t border-white/20 pt-6">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Audio</h2>
        {audioError ? (
          <p className="mt-2 text-sm text-rec">{audioError}</p>
        ) : audioUrl ? (
          <audio
            controls
            src={audioUrl}
            className="mt-3 w-full accent-[#F5F2EA]"
            preload="metadata"
            onError={() => {
              // Direct URL dead (e.g. missing object)? Fall back once to the
              // note's stored audio URL before showing an error.
              if (!audioFellBack && note.audio_url?.startsWith("http") && audioUrl !== note.audio_url) {
                setAudioFellBack(true);
                setAudioUrl(note.audio_url);
              } else {
                setAudioError("Could not load audio.");
              }
            }}
          />
        ) : (
          <p className="mt-2 text-sm text-mute">Loading audio…</p>
        )}
        {note.asr_engine_used && <p className="mt-2 font-mono text-xs text-mute">ASR: {note.asr_engine_used}{note.llm_model_used ? ` · Summary: ${note.llm_model_used}` : ""}</p>}
      </section>

      <section className="border-t border-white/20 pt-6">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Transcript</h2>
        {!note.raw_transcript ? (
          <p className="mt-2 text-sm text-mute">{processing ? "Transcript is being generated…" : "No transcript yet."}</p>
        ) : (
          <>
            <p className="mt-4 max-w-2xl whitespace-pre-wrap font-mono text-sm leading-loose text-paper/90">{note.raw_transcript}</p>
            {note.transcript_segments.length > 1 && (
              <ul className="mt-5 grid gap-3 border-t border-white/20 pt-5">
                {note.transcript_segments.map((s, i) => (
                  <li key={i} className="max-w-2xl font-mono text-sm leading-relaxed">
                    <span className="text-xs text-mute">
                      [{s.start.toFixed(1)}s → {s.end.toFixed(1)}s]
                    </span>{" "}
                    <span className="text-paper/80">{s.text}</span>
                  </li>
                ))}
              </ul>
            )}
          </>
        )}
      </section>

      <section className="border-t border-white/20 pt-6">
        <h2 className="text-lg font-semibold tracking-tight text-paper">Summary</h2>
        {summarizing && (
          <div className="mt-3 max-w-md" role="status" aria-label="Summarizing in progress">
            <div className="indeterminate-track">
              <div className="indeterminate-fill" />
            </div>
            <p className="mt-1.5 text-sm text-mute">Summarizing with AI…</p>
          </div>
        )}
        {!note.summary_tldr ? (
          <p className="mt-2 text-sm text-mute">{processing ? "Summary will appear after transcription…" : "No summary yet."}</p>
        ) : (
          <div className="mt-3 grid max-w-2xl gap-4 text-sm leading-relaxed text-paper/90">
            <p className="text-base">{note.summary_tldr}</p>
            {note.summary_key_points.length > 0 && (
              <div>
                <h3 className="font-medium text-paper">Key points</h3>
                <ul className="mt-1.5 grid gap-1.5">
                  {note.summary_key_points.map((k, i) => (
                    <li key={i} className="flex gap-2"><span className="text-mute">—</span>{k}</li>
                  ))}
                </ul>
              </div>
            )}
            {note.summary_action_items.length > 0 && (
              <div>
                <h3 className="font-medium text-paper">Action items</h3>
                <ul className="mt-1.5 grid gap-1.5">
                  {note.summary_action_items.map((a, i) => (
                    <li key={i} className="flex gap-2"><span className="text-mute">—</span>{a}</li>
                  ))}
                </ul>
              </div>
            )}
            {note.summary_sentiment && <p className="font-mono text-xs text-mute">Sentiment: {note.summary_sentiment}</p>}
          </div>
        )}
      </section>
    </div>
  );
}
