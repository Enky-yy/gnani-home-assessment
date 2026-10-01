// Typed client for the FastAPI backend (backend/app/schemas/audio_note.py).
// Browser calls same-origin /api/* via nginx in compose; direct dev uses absolute base.

export type ProcessingStatus =
  | "UPLOADED"
  | "PREPROCESSING"
  | "TRANSCRIBING"
  | "SUMMARIZING"
  | "COMPLETED"
  | "FAILED";

export interface TranscriptSegment {
  start: number;
  end: number;
  text: string;
  speaker?: string | null;
}

export interface AudioNoteListItem {
  id: string;
  title: string;
  original_filename: string;
  file_size_bytes: number;
  duration_seconds: number | null;
  status: ProcessingStatus;
  progress_percentage: number;
  current_step: string;
  error_message: string | null;
  summary_tldr: string | null;
  summary_sentiment: string | null;
  created_at: string;
  updated_at: string;
}

export interface AudioNoteDetail extends AudioNoteListItem {
  mime_type: string;
  storage_backend: string;
  storage_path: string;
  audio_url: string | null;
  retry_count: number;
  language_code: string;
  asr_engine_used: string | null;
  gnani_job_id: string | null;
  raw_transcript: string | null;
  transcript_segments: TranscriptSegment[];
  summary_key_points: string[];
  summary_action_items: string[];
  llm_model_used: string | null;
}

export interface NoteStatus {
  id: string;
  title: string;
  status: ProcessingStatus;
  progress_percentage: number;
  current_step: string;
  error_message: string | null;
  retry_count: number;
  duration_seconds: number | null;
  updated_at: string | null;
}

const isServer = typeof window === "undefined";
// Browser: same-origin relative /api/* (nginx routes to backend).
// Server (pre-render): needs an absolute URL — internal service name in
// compose, localhost for direct local dev.
const API_BASE = isServer
  ? process.env.BACKEND_INTERNAL_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  : process.env.NEXT_PUBLIC_API_URL || "";

function url(path: string): string {
  // API_BASE empty -> same-origin relative /api/* (nginx routes to backend).
  if (API_BASE) return `${API_BASE.replace(/\/$/, "")}${path}`;
  return path;
}

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body?.detail) detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch {
      try {
        const text = await res.text();
        if (text) detail = text.slice(0, 300);
      } catch {
        /* ignore */
      }
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const TERMINAL_STATUSES: ProcessingStatus[] = ["COMPLETED", "FAILED"];

export function formatDuration(sec: number | null | undefined): string {
  if (sec == null || Number.isNaN(sec)) return "—";
  const s = Math.round(sec);
  const m = Math.floor(s / 60);
  const r = s % 60;
  return m > 0 ? `${m}m ${r}s` : `${r}s`;
}

export function formatBytes(bytes: number): string {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let v = bytes;
  let i = 0;
  while (v >= 1024 && i < units.length - 1) {
    v /= 1024;
    i += 1;
  }
  return `${v.toFixed(v >= 10 || i === 0 ? 0 : 1)} ${units[i]}`;
}

export async function uploadNote(file: File, title?: string, languageCode = "en-IN"): Promise<AudioNoteDetail> {
  const form = new FormData();
  form.append("file", file);
  if (title) form.append("title", title);
  form.append("language_code", languageCode);
  const res = await fetch(url("/api/v1/notes"), { method: "POST", body: form });
  return handle<AudioNoteDetail>(res);
}

export async function listNotes(): Promise<AudioNoteListItem[]> {
  const res = await fetch(url("/api/v1/notes?limit=50"), { cache: "no-store" });
  return handle<AudioNoteListItem[]>(res);
}

export async function getNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}`), { cache: "no-store" });
  return handle<AudioNoteDetail>(res);
}

export async function getNoteStatus(id: string): Promise<NoteStatus> {
  const res = await fetch(url(`/api/v1/notes/${id}/status`), { cache: "no-store" });
  return handle<NoteStatus>(res);
}

export function audioStreamUrl(id: string): string {
  return url(`/api/v1/notes/${id}/audio`);
}

export async function retryNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/retry`), { method: "POST" });
  return handle<AudioNoteDetail>(res);
}

export async function resummarizeNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/summarize`), { method: "POST" });
  return handle<AudioNoteDetail>(res);
}

export async function renameNote(id: string, title: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/title`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
  return handle<AudioNoteDetail>(res);
}

export async function deleteNote(id: string): Promise<void> {
  const res = await fetch(url(`/api/v1/notes/${id}`), { method: "DELETE" });
  return handle<void>(res);
}
