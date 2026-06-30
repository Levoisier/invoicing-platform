"use client";

import { type FormEvent, useState } from "react";

import { useRouter } from "next/navigation";

import { ApiError, api } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  // Dev defaults prefilled so the flow is one click in local dev.
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("admin");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await api.login(username, password);
      router.replace("/invoices");
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "login failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="card" style={{ maxWidth: 360 }}>
      <h1>Log in</h1>
      <form onSubmit={submit}>
        <label>Username</label>
        <input value={username} onChange={(e) => setUsername(e.target.value)} />
        <label>Password</label>
        <input
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        {error && <p className="error">{error}</p>}
        <div style={{ marginTop: 12 }}>
          <button type="submit" disabled={busy}>
            {busy ? "…" : "Log in"}
          </button>
        </div>
      </form>
    </div>
  );
}
