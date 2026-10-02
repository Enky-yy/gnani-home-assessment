"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getNote, getToken, isUnauthorized, logout, type AudioNoteDetail } from "@/lib/api";
import { NoteDetail } from "@/components/note-detail";
import { ErrorBanner } from "@/components/status";

export default function NotePage({ params }: { params: { id: string } }) {
  const router = useRouter();
  const [initial, setInitial] = useState<AudioNoteDetail | null>(null);
  const [ready, setReady] = useState(false);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      router.replace("/login");
      return;
    }
    getNote(params.id)
      .then((note) => {
        setInitial(note);
        setReady(true);
      })
      .catch((err) => {
        if (isUnauthorized(err)) {
          logout();
          router.replace("/login");
          return;
        }
        setNotFound(true);
        setReady(true);
      });
  }, [params.id, router]);

  if (!ready) return <p className="text-sm text-zinc-600">Loading…</p>;
  if (!initial) return <ErrorBanner message={notFound ? "Note not found." : "Could not load note."} />;
  return <NoteDetail id={params.id} initial={initial} />;
}
