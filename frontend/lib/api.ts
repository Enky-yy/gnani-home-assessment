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
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function isUnauthorized(err: unknown): boolean {
  return err instanceof ApiError && err.status === 401;
}

// --- Auth token (localStorage; browser only) ---

const TOKEN_KEY = "audio_notes_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function logout(): void {
  if (typeof window !== "undefined") localStorage.removeItem(TOKEN_KEY);
}

function authHeaders(): Record<string, string> {
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export interface UserRead {
  id: string;
  email: string;
  created_at: string;
}

export async function registerUser(email: string, password: string): Promise<UserRead> {
  const res = await fetch(url("/api/v1/auth/register"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return handle<UserRead>(res);
}

export async function loginUser(email: string, password: string): Promise<string> {
  const res = await fetch(url("/api/v1/auth/login"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const data = await handle<{ access_token: string }>(res);
  setToken(data.access_token);
  return data.access_token;
}

export async function fetchMe(): Promise<UserRead> {
  const res = await fetch(url("/api/v1/auth/me"), { headers: { ...authHeaders() }, cache: "no-store" });
  return handle<UserRead>(res);
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
  const res = await fetch(url("/api/v1/notes"), { method: "POST", headers: { ...authHeaders() }, body: form });
  return handle<AudioNoteDetail>(res);
}

export async function listNotes(): Promise<AudioNoteListItem[]> {
  const res = await fetch(url("/api/v1/notes?limit=50"), { headers: { ...authHeaders() }, cache: "no-store" });
  return handle<AudioNoteListItem[]>(res);
}

export async function getNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}`), { headers: { ...authHeaders() }, cache: "no-store" });
  return handle<AudioNoteDetail>(res);
}

export async function getNoteStatus(id: string): Promise<NoteStatus> {
  const res = await fetch(url(`/api/v1/notes/${id}/status`), { headers: { ...authHeaders() }, cache: "no-store" });
  return handle<NoteStatus>(res);
}

export function audioStreamUrl(id: string): string {
  return url(`/api/v1/notes/${id}/audio`);
}

export async function retryNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/retry`), { method: "POST", headers: { ...authHeaders() } });
  return handle<AudioNoteDetail>(res);
}

export async function resummarizeNote(id: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/summarize`), { method: "POST", headers: { ...authHeaders() } });
  return handle<AudioNoteDetail>(res);
}

export async function renameNote(id: string, title: string): Promise<AudioNoteDetail> {
  const res = await fetch(url(`/api/v1/notes/${id}/title`), {
    method: "PATCH",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ title }),
  });
  return handle<AudioNoteDetail>(res);
}

export async function deleteNote(id: string): Promise<void> {
  const res = await fetch(url(`/api/v1/notes/${id}`), { method: "DELETE", headers: { ...authHeaders() } });
  return handle<void>(res);
}

export async function fetchAudioBlobUrl(id: string): Promise<string> {
  const res = await fetch(url(`/api/v1/notes/${id}/audio`), { headers: { ...authHeaders() } });
  if (!res.ok) {
    const err = await res.text().catch(() => res.statusText);
    throw new ApiError(res.status, err.slice(0, 300));
  }
  const blob = await res.blob();
  return URL.createObjectURL(blob);
}
