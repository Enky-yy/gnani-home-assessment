"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { uploadNote } from "@/lib/api";

const ALLOWED = ["wav", "mp3", "m4a", "ogg", "flac", "aac", "webm"];
// Mirrors backend MAX_UPLOAD_SIZE_MB + nginx client_max_body_size.
const MAX_MB = 500;

export function UploadDropzone() {
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
      router.push(`/notes/${note.id}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold">Upload audio</h2>
      <p className="mt-1 text-sm text-zinc-600">
        Any length — 2 minute recordings and longer are chunked in the background. You get a 202 immediately and can watch progress.
      </p>
      <div className="mt-4 grid gap-3">
        <input
          type="file"
          accept={ALLOWED.map((e) => `.${e}`).join(",")}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          className="text-sm"
          aria-label="Audio file"
        />
        <div className="grid gap-3 sm:grid-cols-2">
          <label className="grid gap-1 text-sm">
            Title (optional)
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="e.g. Team sync Oct 2"
              className="rounded-md border px-3 py-2"
              maxLength={255}
            />
          </label>
          <label className="grid gap-1 text-sm">
            Language
            <select value={language} onChange={(e) => setLanguage(e.target.value)} className="rounded-md border px-3 py-2">
              <option value="en-IN">en-IN</option>
              <option value="hi-IN">hi-IN</option>
              <option value="en">en</option>
            </select>
          </label>
        </div>
        {error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={busy || !file}
          className="rounded-md bg-zinc-900 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Upload and transcribe"}
        </button>
      </div>
    </form>
  );
}
