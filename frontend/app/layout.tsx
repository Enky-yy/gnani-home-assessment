import type { Metadata } from "next";
import Link from "next/link";
import { Inter_Tight, JetBrains_Mono } from "next/font/google";
import { AuthNav } from "@/components/auth-nav";
import "./globals.css";

const grotesk = Inter_Tight({ subsets: ["latin"], variable: "--font-sans" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono" });

export const metadata: Metadata = {
  title: "Audio Notes Platform",
  description: "Upload audio, get Gnani ASR transcripts and LLM summaries.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${grotesk.variable} ${mono.variable}`}>
      <body>
        <header className="border-b border-white/20 bg-void">
          <div className="mx-auto flex max-w-3xl items-center justify-between px-4 py-4">
            <Link href="/" className="text-lg font-semibold tracking-tight text-paper">
              Audio Notes
            </Link>
            <nav className="flex items-center gap-5 text-sm text-mute">
              <Link href="/" className="hover:text-paper">
                Uploads
              </Link>
              <Link href="/architecture" className="hover:text-paper">
                Architecture
              </Link>
              <AuthNav />
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-3xl px-4 py-10">{children}</main>
      </body>
    </html>
  );
}
