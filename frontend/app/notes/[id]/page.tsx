import { getNote } from "@/lib/api";
import { NoteDetail } from "@/components/note-detail";

export const dynamic = "force-dynamic";

export default async function NotePage({ params }: { params: { id: string } }) {
  let initial = null;
  try {
    initial = await getNote(params.id);
  } catch {
    initial = null;
  }
  return <NoteDetail id={params.id} initial={initial} />;
}
