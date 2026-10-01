import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Audio Notes Platform",
  description: "Upload audio, get Gnani ASR transcripts and LLM summaries.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b bg-white">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-3">
            <Link href="/" className="font-semibold tracking-tight">
              Audio Notes
            </Link>
            <nav className="flex gap-4 text-sm text-zinc-600">
              <Link href="/" className="hover:text-zinc-900">
                Uploads
              </Link>
              <Link href="/architecture" className="hover:text-zinc-900">
                Architecture
              </Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-6">{children}</main>
      </body>
    </html>
  );
}
