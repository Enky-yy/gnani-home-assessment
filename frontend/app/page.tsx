"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, isUnauthorized, listNotes, logout, type AudioNoteListItem } from "@/lib/api";
import { UploadDropzone } from "@/components/upload";
import { NotesList } from "@/components/notes-list";

export default function HomePage() {
  const router = useRouter();
  const [notes, setNotes] = useState<AudioNoteListItem[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    listNotes()
      .then(setNotes)
      .catch((err) => {
        if (isUnauthorized(err)) {
          logout();
          router.replace("/login");
          return;
        }
        setLoadError(err instanceof Error ? err.message : "Could not load uploads.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  function refresh() {
    listNotes()
      .then(setNotes)
      .catch((err) => {
        if (isUnauthorized(err)) {
          logout();
          router.replace("/login");
        }
      });
  }

  return (
    <div className="grid gap-6">
      <UploadDropzone onUploaded={refresh} />
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-paper">Past uploads</h2>
        {loading ? (
          <p className="mt-4 font-mono text-sm text-mute">Loading…</p>
        ) : loadError ? (
          <div className="mt-4 rounded border border-rec/40 bg-rec/10 px-3 py-2 text-sm text-paper" role="alert">
            Could not reach the backend: {loadError}
          </div>
        ) : (
          <NotesList notes={notes} />
        )}
      </section>
    </div>
  );
}
