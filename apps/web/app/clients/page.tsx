"use client";

import { type FormEvent, useCallback, useEffect, useState } from "react";

import { type ClientOut, api } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

export default function ClientsPage() {
  const ready = useAuthGuard();
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [form, setForm] = useState({ name: "", tax_id: "", jurisdiction: "CO", address: "" });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .listClients()
      .then(setClients)
      .catch((e) => setError(String(e.message ?? e)));
  }, []);

  useEffect(() => {
    if (ready) load();
  }, [ready, load]);

  async function create(e: FormEvent) {
    e.preventDefault();
    setError(null);
    try {
      await api.createClient({
        name: form.name,
        tax_id: form.tax_id,
        jurisdiction: form.jurisdiction,
        address: form.address || null,
      });
      setForm({ name: "", tax_id: "", jurisdiction: "CO", address: "" });
      load();
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (!ready) return null;

  return (
    <div>
      <h1>Clients</h1>

      <div className="card">
        <h3>New client</h3>
        <form onSubmit={create}>
          <label>Name</label>
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
          <label>NIT / Cédula</label>
          <input value={form.tax_id} onChange={(e) => setForm({ ...form, tax_id: e.target.value })} />
          <label>Jurisdiction</label>
          <input
            value={form.jurisdiction}
            onChange={(e) => setForm({ ...form, jurisdiction: e.target.value })}
          />
          <label>Address (optional)</label>
          <input value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
          {error && <p className="error">{error}</p>}
          <div style={{ marginTop: 12 }}>
            <button type="submit">Create client</button>
          </div>
        </form>
      </div>

      <div className="card">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>NIT/Cédula</th>
              <th>Jurisdiction</th>
            </tr>
          </thead>
          <tbody>
            {clients.map((c) => (
              <tr key={c.id}>
                <td>{c.name}</td>
                <td>{c.tax_id}</td>
                <td>{c.jurisdiction}</td>
              </tr>
            ))}
            {clients.length === 0 && (
              <tr>
                <td colSpan={3}>No clients yet.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}
