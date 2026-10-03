"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { loginUser, registerUser } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!email.includes("@")) {
      setError("Enter a valid email address.");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setBusy(true);
    try {
      if (mode === "register") {
        await registerUser(email.trim(), password);
      }
      await loginUser(email.trim(), password);
      router.push("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Authentication failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto mt-14 max-w-sm">
      <h1 className="text-2xl font-semibold tracking-tight text-paper">{mode === "login" ? "Log in" : "Create account"}</h1>
      <p className="mt-1 text-sm text-mute">Your uploads are private to your account.</p>
      <p className="mt-3 border border-white/10 bg-panel px-3 py-2 font-mono text-xs leading-relaxed text-mute">
        Just looking? <span className="text-paper">demo@example.com</span> / <span className="text-paper">demo1234</span>
      </p>
      <form onSubmit={onSubmit} className="mt-6 grid gap-4">
        <label className="grid gap-1.5 text-sm text-mute">
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="rounded border border-white/15 bg-void px-3 py-2 text-paper"
            autoComplete="email"
          />
        </label>
        <label className="grid gap-1.5 text-sm text-mute">
          Password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="rounded border border-white/15 bg-void px-3 py-2 text-paper"
            autoComplete={mode === "login" ? "current-password" : "new-password"}
          />
        </label>
        {error && (
          <div className="rounded border border-rec/40 bg-rec/10 px-3 py-2 text-sm text-paper" role="alert">
            {error}
          </div>
        )}
        <button
          type="submit"
          disabled={busy}
          className="rounded bg-paper px-4 py-2 text-sm font-medium text-void disabled:opacity-40"
        >
          {busy ? "Please wait…" : mode === "login" ? "Log in" : "Register"}
        </button>
      </form>
      <button
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setError(null);
        }}
        className="mt-4 text-sm text-mute underline hover:text-paper"
      >
        {mode === "login" ? "Need an account? Register" : "Have an account? Log in"}
      </button>
    </div>
  );
}
