"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadNote, isUnauthorized } from "@/lib/api";

const ALLOWED = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm"];
// Mirrors backend MAX_UPLOAD_SIZE_MB + nginx client_max_body_size.
const MAX_MB = 500;

export function UploadDropzone({ onUploaded }: { onUploaded?: () => void }) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [language, setLanguage] = useState("en-IN");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!file) {
      setError("Choose an audio file first.");
      return;
    }
    const ext = file.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED.includes(ext)) {
      setError(`Unsupported format .${ext}. Allowed: ${ALLOWED.join(", ")}.`);
      return;
    }
    if (file.size > MAX_MB * 1024 * 1024) {
      setError(`File is ${(file.size / 1024 / 1024).toFixed(1)} MB. Limit is ${MAX_MB} MB.`);
      return;
    }
    setBusy(true);
    try {
      const note = await uploadNote(file, title.trim() || undefined, language);
      onUploaded?.();
      router.push(`/notes/${note.id}`);
    } catch (err) {
      if (isUnauthorized(err)) {
        router.push("/login");
        return;
      }
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit}>
      <h2 className="text-2xl font-semibold tracking-tight text-paper">Upload audio</h2>
      <p className="mt-1 max-w-xl text-sm leading-relaxed text-mute">
        Any length — long recordings are chunked in the background while you watch.
      </p>
      <div className="mt-5 grid gap-4 border-y border-white/20 py-6">
        <input
          type="file"
          accept={ALLOWED.map((e) => `.${e}`).join(",")}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm text-mute file:mr-3 file:rounded file:border file:border-white/20 file:bg-transparent file:px-3 file:py-1.5 file:text-sm file:text-paper hover:file:border-paper"
          aria-label="Audio file"
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <label className="grid gap-1.5 text-sm text-mute">
            Title (optional)
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Team sync Oct 2"
              className="rounded border border-white/15 bg-void px-3 py-2 text-paper placeholder:text-mute/60"
              maxLength={255}
            />
          </label>
          <label className="grid gap-1.5 text-sm text-mute">
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded border border-white/15 bg-void px-3 py-2 text-paper">
              <option value="en-IN">en-IN</option>
              <option value="hi-IN">hi-IN</option>
              <option value="en">en</option>
            </select>
          </label>
        </div>
        {error && (
          <div className="rounded border border-rec/40 bg-rec/10 px-3 py-2 text-sm text-paper" role="alert">
            {error}
          </div>
        )}
        <div>
          <button
            type="submit"
            disabled={busy || !file}
            className="rounded bg-paper px-5 py-2 text-sm font-medium text-void disabled:opacity-40"
          >
            {busy ? "Uploading…" : "Upload and transcribe"}
          </button>
        </div>
      </div>
    </form>
  );
}
