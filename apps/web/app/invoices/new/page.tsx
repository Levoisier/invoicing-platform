"use client";

import { type FormEvent, useEffect, useState } from "react";

import { useRouter } from "next/navigation";

import { type ClientOut, type LineIn, api } from "@/lib/api";
import { useAuthGuard } from "@/lib/use-auth-guard";

const TAX_CODES = ["iva_19", "iva_5", "excluded"];

type LineForm = { description: string; quantity: string; unit_price: string; tax_code: string };

const emptyLine = (): LineForm => ({
  description: "",
  quantity: "1",
  unit_price: "0",
  tax_code: "iva_19",
});

export default function NewInvoicePage() {
  const ready = useAuthGuard();
  const router = useRouter();
  const [clients, setClients] = useState<ClientOut[]>([]);
  const [clientId, setClientId] = useState<number | "">("");
  const [currency, setCurrency] = useState("COP");
  const [lines, setLines] = useState<LineForm[]>([emptyLine()]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (ready) api.listClients().then(setClients).catch(() => setClients([]));
  }, [ready]);

  function updateLine(i: number, patch: Partial<LineForm>) {
    setLines(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (clientId === "") {
      setError("Pick a client.");
      return;
    }
    try {
      // quantity/unit_price are sent as strings to preserve exact decimals.
      const payloadLines: LineIn[] = lines.map((l) => ({
        description: l.description,
        quantity: l.quantity,
        unit_price: l.unit_price,
        tax_code: l.tax_code,
      }));
      const invoice = await api.createInvoice({
        client_id: clientId,
        currency,
        lines: payloadLines,
      });
      router.push(`/invoices/${invoice.id}`);
    } catch (e) {
      setError(String((e as Error).message));
    }
  }

  if (!ready) return null;

  return (
    <div>
      <h1>New invoice</h1>
      <form onSubmit={submit}>
        <div className="card">
          <label>Client</label>
          <select
            value={clientId}
            onChange={(e) => setClientId(e.target.value ? Number(e.target.value) : "")}
          >
            <option value="">— select —</option>
            {clients.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.jurisdiction})
              </option>
            ))}
          </select>
          <label>Currency</label>
          <input value={currency} onChange={(e) => setCurrency(e.target.value)} />
        </div>

        <div className="card">
          <h3>Lines</h3>
          <table>
            <thead>
              <tr>
                <th>Description</th>
                <th>Qty</th>
                <th>Unit price</th>
                <th>Tax</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={i}>
                  <td>
                    <input
                      value={l.description}
                      onChange={(e) => updateLine(i, { description: e.target.value })}
                    />
                  </td>
                  <td>
                    <input
                      value={l.quantity}
                      onChange={(e) => updateLine(i, { quantity: e.target.value })}
                      style={{ width: 70 }}
                    />
                  </td>
                  <td>
                    <input
                      value={l.unit_price}
                      onChange={(e) => updateLine(i, { unit_price: e.target.value })}
                      style={{ width: 110 }}
                    />
                  </td>
                  <td>
                    <select
                      value={l.tax_code}
                      onChange={(e) => updateLine(i, { tax_code: e.target.value })}
                    >
                      {TAX_CODES.map((code) => (
                        <option key={code} value={code}>
                          {code}
                        </option>
                      ))}
                    </select>
                  </td>
                  <td>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => setLines(lines.filter((_, idx) => idx !== i))}
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <button type="button" className="secondary" onClick={() => setLines([...lines, emptyLine()])}>
            + Add line
          </button>
        </div>

        {error && <p className="error">{error}</p>}
        <button type="submit">Create invoice</button>
      </form>
    </div>
  );
}
