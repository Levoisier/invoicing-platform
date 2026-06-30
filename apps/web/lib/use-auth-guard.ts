"use client";

import { useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import { session } from "./api";

// Client-side guard: a protected page calls this and renders nothing until it
// confirms a token exists, redirecting to /login otherwise. Good enough for a
// single-user dev tool — the API is the real authority (every route requires the
// JWT), this just keeps the UI from flashing protected screens at a logged-out user.
export function useAuthGuard(): boolean {
  const router = useRouter();
  const [ready, setReady] = useState(false);
  useEffect(() => {
    if (session.token) {
      setReady(true);
    } else {
      router.replace("/login");
    }
  }, [router]);
  return ready;
}
