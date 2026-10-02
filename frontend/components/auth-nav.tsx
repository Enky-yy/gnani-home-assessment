"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { fetchMe, getToken, isUnauthorized, logout, type UserRead } from "@/lib/api";

export function AuthNav() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<UserRead | null>(null);
  const [checked, setChecked] = useState(false);

  // Re-check on every navigation: layout persists across route changes,
  // so a mount-only fetch would stay stuck showing the pre-login state.
  useEffect(() => {
    let cancelled = false;
    setChecked(false);
    if (!getToken()) {
      setUser(null);
      setChecked(true);
      return;
    }
    fetchMe()
      .then((u) => {
        if (!cancelled) setUser(u);
      })
      .catch((err) => {
        if (isUnauthorized(err)) logout();
        if (!cancelled) setUser(null);
      })
      .finally(() => {
        if (!cancelled) setChecked(true);
      });
    return () => {
      cancelled = true;
    };
  }, [pathname]);

  function onLogout() {
    logout();
    setUser(null);
    router.push("/login");
  }

  if (!checked) return <span className="text-sm text-zinc-400">…</span>;
  if (!user) {
    return (
      <a href="/login" className="text-sm text-zinc-600 hover:text-zinc-900">
        Log in
      </a>
    );
  }
  return (
    <span className="flex items-center gap-3 text-sm">
      <span className="max-w-40 truncate text-zinc-600" title={user.email}>
        {user.email}
      </span>
      <button onClick={onLogout} className="text-zinc-600 hover:text-zinc-900">
        Log out
      </button>
    </span>
  );
}
