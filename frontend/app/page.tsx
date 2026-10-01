import { listNotes, type AudioNoteListItem } from "@/lib/api";
import { UploadDropzone } from "@/components/upload";
import { NotesList } from "@/components/notes-list";

export const dynamic = "force-dynamic";

export default async function HomePage() {
  let notes: AudioNoteListItem[] = [];
  let loadError: string | null = null;
  try {
    notes = await listNotes();
  } catch (err) {
    loadError = err instanceof Error ? err.message : "Could not load uploads.";
  }

  return (
    <div className="grid gap-6">
      <UploadDropzone />
      <section>
        <h2 className="text-lg font-semibold">Past uploads</h2>
        {loadError ? (
          <div className="mt-2 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800" role="alert">
            Could not reach the backend: {loadError}
          </div>
        ) : (
          <NotesList notes={notes} />
        )}
      </section>
    </div>
  );
}
