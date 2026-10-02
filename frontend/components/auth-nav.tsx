"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { fetchMe, getToken, isUnauthorized, logout, type UserRead } from "@/lib/api";

export function AuthNav() {
  const router = useRouter();
  const [user, setUser] = useState<UserRead | null>(null);
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    if (!getToken()) {
      setChecked(true);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch((err) => {
        if (isUnauthorized(err)) logout();
        setUser(null);
      })
      .finally(() => setChecked(true));
  }, []);

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
